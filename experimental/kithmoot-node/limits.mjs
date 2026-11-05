export const limitSpecifications = [
  ['maxRooms', 'Hosted rooms', [[1, '1 room'], [4, 'Up to 4 rooms'], [8, 'Up to 8 rooms']], 4],
  ['aggregateBytesPerSecond', 'Total call bandwidth', [[1000000, '8 Mbit/s'], [2000000, '16 Mbit/s'], [5000000, '40 Mbit/s']], 2000000],
  ['maxBytes', 'Message storage limit', [[268435456, '256 MiB'], [1073741824, '1 GiB'], [4294967296, '4 GiB']], 1073741824],
  ['minFreeBytes', 'Leave free on this host', [[1073741824, 'At least 1 GiB'], [2147483648, 'At least 2 GiB']], 2147483648]
]
export const pickLimits = value => Object.fromEntries(limitSpecifications.map(([name]) => [name, value[name]]))
export function validLimits(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join() === 'aggregateBytesPerSecond,maxBytes,maxRooms,minFreeBytes'
    && limitSpecifications.every(([name, , options]) => options.some(([number]) => number === value[name]))
}
