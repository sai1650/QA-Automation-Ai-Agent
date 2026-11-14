import axios from 'axios'

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined

export const apiBaseURL = configuredBase ?? '/api/v1'

export const api = axios.create({
  baseURL: apiBaseURL,
  timeout: 20_000,
  headers: { 'Content-Type': 'application/json' },
})

export const healthURL = `${apiBaseURL.replace(/\/api\/v\d+\/?$/, '')}/health`

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (error.code === 'ECONNABORTED') return 'The request timed out. Try again.'
    if (!error.response) return 'Cannot reach the API. Check the backend and API URL.'
    return `The API returned ${error.response.status}.`
  }
  return error instanceof Error ? error.message : 'An unexpected error occurred.'
}
