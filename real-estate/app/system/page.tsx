"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { Navigation } from "@/components/navigation"
import { useToast } from "@/hooks/use-toast"
import { apiClient, type SystemStatus } from "@/lib/api"
import { Play, Square, RefreshCw, Activity, Mail, AlertCircle, CheckCircle } from "lucide-react"

export default function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  const fetchStatus = async () => {
    try {
      setError(null)
      const systemStatus = await apiClient.getSystemStatus()
      setStatus(systemStatus)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch system status"
      setError(errorMessage)
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setInitialLoading(false)
    }
  }

  const handleSystemControl = async (action: "start" | "stop") => {
    setLoading(true)
    try {
      setError(null)
      const result = await apiClient.controlSystem({
        action,
        run_property_matching: true,
        check_email_replies: true,
      })
      setStatus(result)
      toast({
        title: "Success",
        description: `System ${action === "start" ? "started" : "stopped"} successfully`,
      })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : `Failed to ${action} system`
      setError(errorMessage)
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Auto-refresh status every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (running: boolean) => {
    return running ? "bg-green-500 dark:bg-green-600" : "bg-gray-400 dark:bg-gray-500"
  }

  const getStatusText = (running: boolean) => {
    return running ? "Running" : "Stopped"
  }

  if (initialLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <main className="lg:pl-64">
          <div className="px-4 sm:px-6 lg:px-8 py-8">
            <div className="max-w-7xl mx-auto">
              <div className="flex items-center justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            </div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="lg:pl-64">
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          <div className="max-w-7xl mx-auto">
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-foreground">System Dashboard</h1>
              <p className="text-muted-foreground mt-2">Monitor and control the property matching system</p>
            </div>

            {error && (
              <Alert className="mb-6" variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* System Status Card */}
              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">System Status</CardTitle>
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(status?.running || false)}`} />
                    <Badge variant={status?.running ? "default" : "secondary"}>
                      {getStatusText(status?.running || false)}
                    </Badge>
                  </div>
                  {status?.timestamp && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Last updated: {new Date(status.timestamp).toLocaleString()}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Last Property Match Card */}
              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Last Property Match</CardTitle>
                  <CheckCircle className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {status?.last_property_match ? (
                      <span className="text-green-600 dark:text-green-400">
                        {new Date(status.last_property_match).toLocaleDateString()}
                      </span>
                    ) : (
                      <span className="text-foreground">No matches yet</span>
                    )}
                  </div>
                  <p className="text-xs text-foreground opacity-70">
                    {status?.last_property_match
                      ? `at ${new Date(status.last_property_match).toLocaleTimeString()}`
                      : "System hasn't run property matching"}
                  </p>
                </CardContent>
              </Card>

              {/* Last Email Check Card */}
              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Last Email Check</CardTitle>
                  <Mail className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {status?.last_email_check ? (
                      <span className="text-blue-600 dark:text-blue-400">
                        {new Date(status.last_email_check).toLocaleDateString()}
                      </span>
                    ) : (
                      <span className="text-foreground">No checks yet</span>
                    )}
                  </div>
                  <p className="text-xs text-foreground opacity-70">
                    {status?.last_email_check
                      ? `at ${new Date(status.last_email_check).toLocaleTimeString()}`
                      : "System hasn't checked emails"}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* System Controls */}
            <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
              <CardHeader>
                <CardTitle className="text-foreground">System Controls</CardTitle>
                <CardDescription className="text-muted-foreground">
                  Start or stop the property matching system. The system will automatically match properties to clients
                  and check for email replies.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4">
                  <Button
                    onClick={() => handleSystemControl("start")}
                    disabled={loading || status?.running}
                    className="flex items-center space-x-2 transition-all"
                  >
                    {loading ? <LoadingSpinner size="sm" /> : <Play className="h-4 w-4" />}
                    <span className="text-primary-foreground">Start System</span>
                  </Button>

                  <Button
                    onClick={() => handleSystemControl("stop")}
                    disabled={loading || !status?.running}
                    variant="destructive"
                    className="flex items-center space-x-2 transition-all"
                  >
                    {loading ? <LoadingSpinner size="sm" /> : <Square className="h-4 w-4" />}
                    <span className="text-destructive-foreground">Stop System</span>
                  </Button>

                  <Button
                    onClick={fetchStatus}
                    disabled={loading}
                    variant="outline"
                    className="flex items-center space-x-2 transition-all bg-transparent border-border hover:bg-accent hover:text-accent-foreground"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                    <span className="text-foreground">Refresh Status</span>
                  </Button>
                </div>

                {status?.error && (
                  <Alert className="mt-4" variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>System Error: {status.error}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* System Information */}
            <Card className="mt-6 transition-all hover:shadow-md dark:hover:shadow-lg">
              <CardHeader>
                <CardTitle>System Information</CardTitle>
                <CardDescription>Current system configuration and operational details</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">Features Enabled</h4>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline" className="transition-colors">
                        Property Matching
                      </Badge>
                      <Badge variant="outline" className="transition-colors">
                        Email Monitoring
                      </Badge>
                      <Badge variant="outline" className="transition-colors">
                        Client Notifications
                      </Badge>
                      <Badge variant="outline" className="transition-colors">
                        Meeting Scheduling
                      </Badge>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">System Health</h4>
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full" />
                      <span className="text-sm text-muted-foreground">All services operational</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
