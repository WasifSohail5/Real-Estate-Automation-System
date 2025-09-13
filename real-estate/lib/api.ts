const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8006"

export interface SystemStatus {
  status: string
  timestamp: string
  running: boolean
  last_property_match?: string
  last_email_check?: string
  error?: string
}

export interface SystemControl {
  action: "start" | "stop" | "status"
  run_property_matching?: boolean
  check_email_replies?: boolean
}

export class ApiClient {
  private baseUrl: string

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8006"

    if (!this.baseUrl || this.baseUrl === "undefined") {
      this.baseUrl = "http://localhost:8006"
    }

    console.log("[v0] ApiClient initialized with baseUrl:", this.baseUrl)
  }

  async getSystemStatus(): Promise<SystemStatus> {
    try {
      console.log("[v0] Attempting to fetch system status from:", this.baseUrl)

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)

      const response = await fetch(`${this.baseUrl}/api/system/status`, {
        signal: controller.signal,
        mode: "cors",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      console.log("[v0] Successfully fetched system status:", data)
      return data
    } catch (error) {
      console.log("[v0] Failed to fetch system status:", error)
      if (error instanceof Error) {
        if (error.name === "AbortError") {
          throw new Error("Request timeout - please check if the backend server is running")
        }
        if (error.message.includes("Failed to fetch") || error.message.includes("CORS")) {
          throw new Error(`CORS Error: Cannot connect to backend server at ${this.baseUrl}. 

Please add CORS middleware to your FastAPI backend:

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)`)
        }
      }
      throw error
    }
  }

  async controlSystem(control: SystemControl): Promise<SystemStatus> {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000)

      const response = await fetch(`${this.baseUrl}/api/system/control`, {
        method: "POST",
        signal: controller.signal,
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(control),
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      return response.json()
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === "AbortError") {
          throw new Error("Request timeout - operation may still be processing")
        }
        if (error.message.includes("Failed to fetch") || error.message.includes("CORS")) {
          throw new Error(
            `CORS Error: Cannot connect to backend server at ${this.baseUrl}. Please ensure CORS is configured in your FastAPI backend.`,
          )
        }
      }
      throw error
    }
  }
}

export const apiClient = new ApiClient("http://localhost:8006")
