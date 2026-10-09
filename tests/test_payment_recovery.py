"""Synthetic recovery failures must preserve uncertainty and restart storage."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).parents[1] / 'scripts/recover-wildbloom-payment.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'wildbloom-node'
        (self.root / 'operator/checkout').mkdir(parents=True, mode=0o700)
        for p in [self.root, self.root/'operator']:
            p.chmod(0o700)
        self.db = self.root / 'operator/checkout/checkout.sqlite3'
        self.order('lnurl_pending')
        self.settings = self.base/'settings.json'
        r.save(self.settings, {'active': {'revision':2, 'checkout_started':True, 'origin':'https://node.example:3742',
            'settings': {'quota_bytes':10000, 'max_blob_bytes':1000}}})
        r.save(self.root/'operator/dashboard-profile-2.json', {'state':'/data/operator/checkout',
            'checkout':{'origin':'https://node.example:3742/'},'phoenixd':None,'notes':[]})
        self.calls = []
        self.running = True
        self.fail_recovery = False
        self.fail_restart = False
        self.backed_up = False
    def order(self, state):
        with sqlite3.connect(self.db) as db:
            db.execute('PRAGMA user_version=1')
            db.execute('CREATE TABLE IF NOT EXISTS orders(id TEXT, state TEXT, quote TEXT)')
            db.execute('DELETE FROM orders')
            db.execute('INSERT INTO orders VALUES(?,?,?)', ('order-a',state,json.dumps({'order_id':'order-a','rail':'lnurlcash'})))
        self.db.chmod(0o600)
    def execute(self, args, **kwargs):
        self.calls.append(args)
        if args[0] == 'curl':
            return '{"status":"ok"}'
        if args[:2] == ['podman','inspect']:
            return json.dumps([{'State':{'Running':True},'ImageName':r.IMAGE,'Image':'ab'*32,
                'Mounts':[{'Destination':'/data','Source':str(self.root),'RW':True}],
                'Config':{'Env':['WILDBLOOM_CHECKOUT_PROFILE=/data/operator/dashboard-profile-2.json',
                  'WILDBLOOM_ARCHIPELAGO_SETTINGS_REVISION=2','WILDBLOOM_QUOTA_BYTES=10000','WILDBLOOM_MAX_BLOB_BYTES=1000']}}])
        if args[:3] == ['systemctl','--user','show']:
            return 'loaded\n'
        if args[:2] == ['podman','ps']:
            return 'wildbloom-node\n' if self.running else ''
        if args[:3] == ['systemctl','--user','stop']:
            self.running=False
        if args[:3] == ['systemctl','--user','start']:
            if self.fail_restart: raise r.Refused('failed restart')
            self.running=True
        if args[:2] == ['podman','run']:
            self.assertFalse(self.running)
            self.assertTrue(self.backed_up)
            self.assertIn('--pull=never',args)
            self.assertIn('ab'*32,args)
            if self.fail_recovery: raise TimeoutError('secret mutation URL must not be exposed')
            self.order('active')
            return '"active"'
        return ''
    def backup(self, root, destination):
        self.assertFalse(self.running)
        r.backup(root,destination)
        self.backed_up=True
    def recover(self):
        return r.recover(self.root,self.settings,'reconcile','order-a',self.execute,self.backup)
    def journals(self):
        return [json.loads(p.read_text()) for p in (self.root/'operator/recovery').glob('*.json') if not p.name.endswith('-profile.json')]
    def test_success_uses_existing_operation_and_keeps_verified_backup(self):
        result=self.recover()
        self.assertEqual(result['order_state'],'active')
        self.assertTrue(self.running)
        mask = self.calls.index(['systemctl','--user','mask','--runtime',r.SERVICE])
        stop = self.calls.index(['systemctl','--user','stop',r.SERVICE])
        unmask = self.calls.index(['systemctl','--user','unmask','--runtime',r.SERVICE])
        start = self.calls.index(['systemctl','--user','start',r.SERVICE])
        self.assertLess(mask,stop); self.assertLess(stop,unmask); self.assertLess(unmask,start)
        self.assertTrue(Path(result['backup']).is_dir())
        self.assertEqual(self.journals()[0]['status'],'completed')
        self.assertFalse(any('lightning' in args or 'lnurlcash' in args for args in self.calls))
    def test_uncertain_timeout_restarts_and_preserves_pending_order(self):
        self.fail_recovery=True
        with self.assertRaises(TimeoutError): self.recover()
        self.assertTrue(self.running)
        self.assertEqual(r.read_order(self.root,'order-a')[0],'lnurl_pending')
        self.assertEqual(self.journals()[0]['status'],'needs_review')
        self.assertNotIn('secret',json.dumps(self.journals()))
        self.fail_recovery=False
        self.assertEqual(self.recover()['order_state'],'active')
    def test_restart_failure_is_distinct_from_payment_failure(self):
        self.fail_restart=True
        with self.assertRaisesRegex(r.Refused,'restart could not be verified'): self.recover()
        self.assertEqual(r.read_order(self.root,'order-a')[0],'active')
        self.assertEqual(self.journals()[0]['status'],'restart_required')
    def test_reservations_and_terminal_orders_never_stop_the_node(self):
        for state in ['reserving','quoted','active','refund_required','expired']:
            self.order(state)
            with self.assertRaises(r.Refused): self.recover()
        self.assertEqual(self.calls,[])
    def test_backup_failure_never_contacts_receiver_and_restarts(self):
        def fail(*args): raise r.Refused('backup failed')
        with self.assertRaises(r.Refused):
            r.recover(self.root,self.settings,'reconcile','order-a',self.execute,fail)
        self.assertTrue(self.running)
        self.assertFalse(any(c[:2]==['podman','run'] for c in self.calls))
    def test_invalid_id_and_public_state_refused(self):
        with self.assertRaises(r.Refused): r.recover(self.root,self.settings,'reconcile','../x',self.execute)
        self.db.chmod(0o644)
        with self.assertRaises(r.Refused): self.recover()
        self.assertFalse(self.calls)
    def test_backup_refuses_symlinks(self):
        (self.root/'leak').symlink_to(self.settings)
        with self.assertRaises(r.Refused): self.recover()
        self.assertTrue(self.running)
        self.assertFalse(any(c[:2]==['podman','run'] for c in self.calls))

if __name__ == '__main__':
    unittest.main()
