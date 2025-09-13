"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { Navigation } from "@/components/navigation"
import { apiClient, type SystemStatus } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { Activity, Users, Building2, Calendar, Mail, TrendingUp, ArrowRight, Play, Square } from "lucide-react"

// Mock data for dashboard overview
const mockStats = {
  totalClients: 24,
  activeProperties: 18,
  scheduledMeetings: 7,
  emailsSent: 156,
  propertyMatches: 42,
  completedMeetings: 15,
}

const mockRecentActivity = [
  {
    id: 1,
    type: "property_match",
    message: "New property match found for Sarah Johnson",
    timestamp: "2024-01-15T10:30:00Z",
    icon: Building2,
  },
  {
    id: 2,
    type: "meeting",
    message: "Meeting scheduled with Michael Chen for tomorrow",
    timestamp: "2024-01-15T09:15:00Z",
    icon: Calendar,
  },
  {
    id: 3,
    type: "email",
    message: "Property details sent to Emily Rodriguez",
    timestamp: "2024-01-14T16:45:00Z",
    icon: Mail,
  },
  {
    id: 4,
    type: "client",
    message: "New client David Thompson added to system",
    timestamp: "2024-01-14T14:20:00Z",
    icon: Users,
  },
]

const mockUpcomingMeetings = [
  {
    id: 1,
    clientName: "Sarah Johnson",
    propertyTitle: "Modern Downtown Condo",
    date: "2024-01-16",
    time: "14:00",
  },
  {
    id: 2,
    clientName: "Michael Chen",
    propertyTitle: "Luxury Bellevue Estate",
    date: "2024-01-17",
    time: "10:30",
  },
  {
    id: 3,
    clientName: "David Thompson",
    propertyTitle: "Family Home in Fremont",
    date: "2024-01-18",
    time: "11:00",
  },
]

export default function HomePage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const { toast } = useToast()

  const fetchSystemStatus = async () => {
    try {
      console.log("[v0] Attempting to fetch system status from:", process.env.API_BASE_URL)
      const status = await apiClient.getSystemStatus()
      console.log("[v0] System status fetched successfully:", status)
      setSystemStatus(status)
    } catch (error) {
      console.error("[v0] Failed to fetch system status:", error)
      setSystemStatus({
        status: "disconnected",
        timestamp: new Date().toISOString(),
        running: false,
        error: error instanceof Error ? error.message : "Unknown error occurred",
      })
    } finally {
      setInitialLoading(false)
    }
  }

  const handleSystemControl = async (action: "start" | "stop") => {
    setLoading(true)
    try {
      console.log("[v0] Attempting system control action:", action)
      const result = await apiClient.controlSystem({
        action,
        run_property_matching: true,
        check_email_replies: true,
      })
      console.log("[v0] System control successful:", result)
      setSystemStatus(result)
      toast({
        title: "Success",
        description: `System ${action === "start" ? "started" : "stopped"} successfully`,
      })
    } catch (error) {
      console.error("[v0] System control failed:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : `Failed to ${action} system`,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSystemStatus()
  }, [])

  const formatTime = (time: string) => {
    const [hours, minutes] = time.split(":")
    const hour = Number.parseInt(hours)
    const ampm = hour >= 12 ? "PM" : "AM"
    const displayHour = hour % 12 || 12
    return `${displayHour}:${minutes} ${ampm}`
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
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-foreground">Dashboard Overview</h1>
              <p className="text-muted-foreground mt-2">Welcome to your real estate management system</p>
            </div>

            {/* System Status Card */}
            <Card className="mb-8 transition-all hover:shadow-md dark:hover:shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-primary" />
                  System Status
                </CardTitle>
                <CardDescription>Current system operational status and controls</CardDescription>
              </CardHeader>
              <CardContent>
                {systemStatus?.error && (
                  <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg">
                    <p className="text-sm text-red-800 dark:text-red-200 font-medium">Connection Error</p>
                    <p className="text-xs text-red-700 dark:text-red-300 mt-1">{systemStatus.error}</p>
                    <Button
                      onClick={fetchSystemStatus}
                      size="sm"
                      variant="outline"
                      className="mt-2 border-red-300 dark:border-red-700 text-red-800 dark:text-red-200 hover:bg-red-100 dark:hover:bg-red-900/50 bg-transparent"
                    >
                      Retry Connection
                    </Button>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <div
                        className={`w-3 h-3 rounded-full transition-colors ${
                          systemStatus?.running
                            ? "bg-green-500 dark:bg-green-400"
                            : systemStatus?.error
                              ? "bg-red-500 dark:bg-red-400"
                              : "bg-gray-400 dark:bg-gray-500"
                        }`}
                      />
                      <Badge
                        variant={systemStatus?.running ? "default" : systemStatus?.error ? "destructive" : "secondary"}
                        className="transition-colors"
                      >
                        {systemStatus?.error ? "Disconnected" : systemStatus?.running ? "Running" : "Stopped"}
                      </Badge>
                    </div>
                    {systemStatus?.timestamp && (
                      <span className="text-sm text-muted-foreground">
                        Last updated: {new Date(systemStatus.timestamp).toLocaleString()}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleSystemControl("start")}
                      disabled={loading || systemStatus?.running || !!systemStatus?.error}
                      size="sm"
                      className="transition-all"
                    >
                      {loading ? <LoadingSpinner size="sm" /> : <Play className="h-4 w-4 mr-1" />}
                      Start
                    </Button>
                    <Button
                      onClick={() => handleSystemControl("stop")}
                      disabled={loading || !systemStatus?.running || !!systemStatus?.error}
                      variant="destructive"
                      size="sm"
                      className="transition-all"
                    >
                      {loading ? <LoadingSpinner size="sm" /> : <Square className="h-4 w-4 mr-1" />}
                      Stop
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Clients</CardTitle>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{mockStats.totalClients}</div>
                  <p className="text-xs text-muted-foreground">+2 from last week</p>
                </CardContent>
              </Card>

              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Active Properties</CardTitle>
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{mockStats.activeProperties}</div>
                  <p className="text-xs text-muted-foreground">+3 new listings</p>
                </CardContent>
              </Card>

              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Scheduled Meetings</CardTitle>
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{mockStats.scheduledMeetings}</div>
                  <p className="text-xs text-muted-foreground">This week</p>
                </CardContent>
              </Card>

              <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Property Matches</CardTitle>
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{mockStats.propertyMatches}</div>
                  <p className="text-xs text-muted-foreground">+8 this month</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Recent Activity */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    Recent Activity
                    <Button variant="ghost" size="sm">
                      View All
                      <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </CardTitle>
                  <CardDescription>Latest system activities and updates</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {mockRecentActivity.map((activity) => (
                      <div key={activity.id} className="flex items-start space-x-3">
                        <div className="p-2 bg-muted rounded-lg">
                          <activity.icon className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{activity.message}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(activity.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Upcoming Meetings */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    Upcoming Meetings
                    <Button variant="ghost" size="sm">
                      View All
                      <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </CardTitle>
                  <CardDescription>Scheduled property viewings and consultations</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {mockUpcomingMeetings.map((meeting) => (
                      <div key={meeting.id} className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 bg-muted rounded-lg">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="text-sm font-medium">{meeting.clientName}</p>
                            <p className="text-xs text-muted-foreground">{meeting.propertyTitle}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-medium">{new Date(meeting.date).toLocaleDateString()}</p>
                          <p className="text-xs text-muted-foreground">{formatTime(meeting.time)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Quick Actions */}
            <Card className="transition-all hover:shadow-md dark:hover:shadow-lg">
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
                <CardDescription>Frequently used features and shortcuts</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Button variant="outline" className="h-20 flex-col bg-transparent transition-all hover:scale-105">
                    <Users className="h-6 w-6 mb-2" />
                    <span>Add Client</span>
                  </Button>
                  <Button variant="outline" className="h-20 flex-col bg-transparent transition-all hover:scale-105">
                    <Building2 className="h-6 w-6 mb-2" />
                    <span>Add Property</span>
                  </Button>
                  <Button variant="outline" className="h-20 flex-col bg-transparent transition-all hover:scale-105">
                    <Calendar className="h-6 w-6 mb-2" />
                    <span>Schedule Meeting</span>
                  </Button>
                  <Button variant="outline" className="h-20 flex-col bg-transparent transition-all hover:scale-105">
                    <Mail className="h-6 w-6 mb-2" />
                    <span>Send Email</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
