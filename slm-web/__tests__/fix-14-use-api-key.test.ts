/**
 * Fix 14: use-api-key hook + auto-attach to requests
 * Create hooks/use-api-key.ts with localStorage-backed API key state
 *
 * RED  - tests expect the hook to exist and manage API key state
 * GREEN - create the hook
 */
import { describe, it, expect, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useApiKey } from "@/hooks/use-api-key"

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    get length() {
      return Object.keys(store).length
    },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
  }
})()

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  writable: true,
})

describe("Fix 14 - useApiKey hook", () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  it("returns empty string when no key is stored", () => {
    const { result } = renderHook(() => useApiKey())
    expect(result.current.apiKey).toBe("")
  })

  it("loads key from localStorage on mount", () => {
    localStorageMock.setItem("slm-api-key", "slm_test123")
    const { result } = renderHook(() => useApiKey())
    expect(result.current.apiKey).toBe("slm_test123")
  })

  it("setKey stores key in localStorage and updates state", () => {
    const { result } = renderHook(() => useApiKey())
    act(() => {
      result.current.setKey("slm_newkey456")
    })
    expect(result.current.apiKey).toBe("slm_newkey456")
    expect(localStorageMock.getItem("slm-api-key")).toBe("slm_newkey456")
  })

  it("clearKey removes key from localStorage and resets state", () => {
    localStorageMock.setItem("slm-api-key", "slm_existing")
    const { result } = renderHook(() => useApiKey())
    expect(result.current.apiKey).toBe("slm_existing")

    act(() => {
      result.current.clearKey()
    })
    expect(result.current.apiKey).toBe("")
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("slm-api-key")
  })

  it("exposes setKey, clearKey, and apiKey", () => {
    const { result } = renderHook(() => useApiKey())
    expect(typeof result.current.setKey).toBe("function")
    expect(typeof result.current.clearKey).toBe("function")
    expect(typeof result.current.apiKey).toBe("string")
  })
})
