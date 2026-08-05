export interface RafScheduler<T extends unknown[]> {
  schedule: (...args: T) => void
  cancel: () => void
}

export interface DebouncedTask<T extends unknown[]> {
  schedule: (...args: T) => void
  cancel: () => void
  flush: () => void
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

export function createDebouncedTask<T extends unknown[]>(callback: (...args: T) => void, delayMs: number): DebouncedTask<T> {
  let timer: ReturnType<typeof setTimeout> | null = null
  let latestArgs: T | null = null

  function cancel() {
    if (timer) clearTimeout(timer)
    timer = null
    latestArgs = null
  }

  function flush() {
    if (timer) clearTimeout(timer)
    timer = null
    const pending = latestArgs
    latestArgs = null
    if (pending) callback(...pending)
  }

  function schedule(...args: T) {
    latestArgs = args
    if (timer) clearTimeout(timer)
    timer = setTimeout(flush, delayMs)
  }

  return { schedule, cancel, flush }
}
