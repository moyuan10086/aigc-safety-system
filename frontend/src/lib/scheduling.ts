export interface RafScheduler<T extends unknown[]> {
  schedule: (...args: T) => void
  cancel: () => void
}

export function createRafScheduler<T extends unknown[]>(callback: (...args: T) => void): RafScheduler<T> {
  let frame: number | null = null
  let latestArgs: T | null = null

  function cancel() {
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    latestArgs = null
  }

  function schedule(...args: T) {
    latestArgs = args
    if (frame !== null) return
    frame = requestAnimationFrame(() => {
      frame = null
      const pending = latestArgs
      latestArgs = null
      if (pending) callback(...pending)
    })
  }

  return { schedule, cancel }
}
