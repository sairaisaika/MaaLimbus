export const SINNERS = ['Yi Sang', 'Faust', 'Don Quixote', 'Ryoshu', 'Meursault', 'Hong Lu', 'Heathcliff', 'Ishmael', 'Rodion', 'Sinclair', 'Outis', 'Gregor'];
export function toggleSinner(order: string[], name: string): string[] {
  if (!SINNERS.includes(name)) throw new Error('Unknown sinner');
  return order.includes(name) ? order.filter(n => n !== name) : [...order, name];
}
export function moveSinner(order: string[], index: number, direction: number): string[] {
  const next = [...order], target = index + direction;
  if (index < 0 || index >= order.length || target < 0 || target >= order.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
export function completeOrder(order: string[]): boolean {
  return order.length === 12 && new Set(order).size === 12 && order.every(n => SINNERS.includes(n));
}
