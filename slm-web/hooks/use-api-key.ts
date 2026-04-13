"use client"

import * as React from "react"

const STORAGE_KEY = "slm-api-key"

interface UseApiKeyReturn {
  apiKey: string
  setKey: (key: string) => void
  clearKey: () => void
}

export function useApiKey(): UseApiKeyReturn {
  const [apiKey, setApiKey] = React.useState<string>(() => {
    if (typeof window === "undefined") return ""
    return localStorage.getItem(STORAGE_KEY) ?? ""
  })

  const setKey = React.useCallback((key: string) => {
    const trimmed = key.trim()
    localStorage.setItem(STORAGE_KEY, trimmed)
    setApiKey(trimmed)
  }, [])

  const clearKey = React.useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setApiKey("")
  }, [])

  return { apiKey, setKey, clearKey }
}
