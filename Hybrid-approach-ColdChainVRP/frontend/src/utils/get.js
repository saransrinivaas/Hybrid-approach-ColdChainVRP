// Custom ESM implementation of get to resolve esbuild pre-bundling collisions
export function get(object, path, defaultValue) {
  if (object == null) return defaultValue;

  // Handle path array or dot-notation string
  const pathArray = Array.isArray(path)
    ? path
    : typeof path === 'string'
      ? path.replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean)
      : [path];

  let current = object;
  for (const key of pathArray) {
    if (current == null) return defaultValue;
    
    // Prototype pollution protection
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      return defaultValue;
    }
    
    current = current[key];
  }

  return current === undefined ? defaultValue : current;
}

export default get;
