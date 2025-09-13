"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Navigation } from "@/components/navigation"
import { Search, Calendar, Clock, MapPin, User, Plus, Phone, Mail, Building2 } from "lucide-react"

// Mock meetings data
const mockMeetings = [
  {
    id: 1,
    clientId: 1,
    clientName: "Sarah Johnson",
    clientEmail: "sarah.johnson@email.com",
    clientPhone: "(555) 123-4567",
    propertyTitle: "Modern Downtown Condo",
    propertyAddress: "123 Pine St, Seattle, WA 98101",
    meetingDate: "2024-01-16",
    meetingTime: "14:00",
    officeName: "Downtown Seattle Office",
    officeAddress: "456 1st Ave, Seattle, WA 98104",
    status: "scheduled",
    notes: "First-time buyer, interested in modern amenities and city views.",
    createdAt: "2024-01-15T10:30:00Z",
  },
  {
    id: 2,
    clientId: 2,
    clientName: "Michael Chen",
    clientEmail: "m.chen@email.com",
    clientPhone: "(555) 234-5678",
    propertyTitle: "Luxury Bellevue Estate",
    propertyAddress: "456 Bellevue Way, Bellevue, WA 98004",
    meetingDate: "2024-01-17",
    meetingTime: "10:30",
    officeName: "Bellevue Office",
    officeAddress: "789 Bellevue Square, Bellevue, WA 98004",
    status: "scheduled",
    notes: "Looking for luxury features, has specific requirements for home office space.",
    createdAt: "2024-01-14T16:45:00Z",
  },
  {
    id: 3,
    clientId: 3,
    clientName: "Emily Rodriguez",
    clientEmail: "emily.r@email.com",
    clientPhone: "(555) 345-6789",
    propertyTitle: "Historic Capitol Hill Townhouse",
    propertyAddress: "789 Broadway, Seattle, WA 98102",
    meetingDate: "2024-01-15",
    meetingTime: "16:00",
    officeName: "Capitol Hill Office",
    officeAddress: "321 Broadway E, Seattle, WA 98102",
    status: "completed",
    notes: "Loves historic properties, concerned about maintenance costs.",
    createdAt: "2024-01-12T09:15:00Z",
  },
  {
    id: 4,
    clientId: 4,
    clientName: "David Thompson",
    clientEmail: "d.thompson@email.com",
    clientPhone: "(555) 456-7890",
    propertyTitle: "Family Home in Fremont",
    propertyAddress: "321 Fremont Ave, Seattle, WA 98103",
    meetingDate: "2024-01-18",
    meetingTime: "11:00",
    officeName: "North Seattle Office",
    officeAddress: "654 N 45th St, Seattle, WA 98103",
    status: "scheduled",
    notes: "Family with two children, needs good school district and safe neighborhood.",
    createdAt: "2024-01-13T14:20:00Z",
  },
  {
    id: 5,
    clientId: 1,
    clientName: "Sarah Johnson",
    clientEmail: "sarah.johnson@email.com",
    clientPhone: "(555) 123-4567",
    propertyTitle: "Consultation Meeting",
    propertyAddress: null,
    meetingDate: "2024-01-12",
    meetingTime: "13:00",
    officeName: "Downtown Seattle Office",
    officeAddress: "456 1st Ave, Seattle, WA 98104",
    status: "completed",
    notes: "Initial consultation to understand preferences and budget.",
    createdAt: "2024-01-10T11:00:00Z",
  },
]

export default function MeetingsPage() {
  const [searchTerm, setSearchTerm] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [dateFilter, setDateFilter] = useState("all")

  const filteredMeetings = useMemo(() => {
    return mockMeetings.filter((meeting) => {
      const matchesSearch =
        meeting.clientName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        meeting.propertyTitle?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        meeting.officeName.toLowerCase().includes(searchTerm.toLowerCase())

      const matchesStatus = statusFilter === "all" || meeting.status === statusFilter

      const today = new Date()
      const meetingDate = new Date(meeting.meetingDate)
      let matchesDate = true

      if (dateFilter === "today") {
        matchesDate = meetingDate.toDateString() === today.toDateString()
      } else if (dateFilter === "upcoming") {
        matchesDate = meetingDate >= today
      } else if (dateFilter === "past") {
        matchesDate = meetingDate < today
      }

      return matchesSearch && matchesStatus && matchesDate
    })
  }, [searchTerm, statusFilter, dateFilter])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "scheduled":
        return "bg-blue-100 text-blue-800 border-blue-200"
      case "completed":
        return "bg-green-100 text-green-800 border-green-200"
      case "cancelled":
        return "bg-red-100 text-red-800 border-red-200"
      case "rescheduled":
        return "bg-yellow-100 text-yellow-800 border-yellow-200"
      default:
        return "bg-gray-100 text-gray-800 border-gray-200"
    }
  }

  const formatTime = (time: string) => {
    const [hours, minutes] = time.split(":")
    const hour = Number.parseInt(hours)
    const ampm = hour >= 12 ? "PM" : "AM"
    const displayHour = hour % 12 || 12
    return `${displayHour}:${minutes} ${ampm}`
  }

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  }

  // Group meetings by date for calendar view
  const meetingsByDate = useMemo(() => {
    const grouped = filteredMeetings.reduce(
      (acc, meeting) => {
        const date = meeting.meetingDate
        if (!acc[date]) {
          acc[date] = []
        }
        acc[date].push(meeting)
        return acc
      },
      {} as Record<string, typeof mockMeetings>,
    )

    // Sort dates
    return Object.keys(grouped)
      .sort()
      .reduce(
        (acc, date) => {
          acc[date] = grouped[date].sort((a, b) => a.meetingTime.localeCompare(b.meetingTime))
          return acc
        },
        {} as Record<string, typeof mockMeetings>,
      )
  }, [filteredMeetings])

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="lg:pl-64">
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold text-foreground">Meetings</h1>
                <p className="text-muted-foreground mt-2">Schedule and manage property viewings and consultations</p>
              </div>
              <Button className="mt-4 sm:mt-0">
                <Plus className="h-4 w-4 mr-2" />
                Schedule Meeting
              </Button>
            </div>

            {/* Search and Filter Controls */}
            <div className="flex flex-col lg:flex-row gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search meetings by client, property, or office..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <div className="flex gap-1">
                  <Button
                    variant={statusFilter === "all" ? "default" : "outline"}
                    onClick={() => setStatusFilter("all")}
                    size="sm"
                  >
                    All Status
                  </Button>
                  <Button
                    variant={statusFilter === "scheduled" ? "default" : "outline"}
                    onClick={() => setStatusFilter("scheduled")}
                    size="sm"
                  >
                    Scheduled
                  </Button>
                  <Button
                    variant={statusFilter === "completed" ? "default" : "outline"}
                    onClick={() => setStatusFilter("completed")}
                    size="sm"
                  >
                    Completed
                  </Button>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant={dateFilter === "all" ? "default" : "outline"}
                    onClick={() => setDateFilter("all")}
                    size="sm"
                  >
                    All Dates
                  </Button>
                  <Button
                    variant={dateFilter === "today" ? "default" : "outline"}
                    onClick={() => setDateFilter("today")}
                    size="sm"
                  >
                    Today
                  </Button>
                  <Button
                    variant={dateFilter === "upcoming" ? "default" : "outline"}
                    onClick={() => setDateFilter("upcoming")}
                    size="sm"
                  >
                    Upcoming
                  </Button>
                </div>
              </div>
            </div>

            <Tabs defaultValue="list" className="space-y-6">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="list" className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  List View
                </TabsTrigger>
                <TabsTrigger value="calendar" className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  Calendar View
                </TabsTrigger>
              </TabsList>

              <TabsContent value="list" className="space-y-4">
                {filteredMeetings.map((meeting) => (
                  <Card key={meeting.id} className="hover:shadow-md transition-shadow">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <User className="h-5 w-5 text-primary" />
                            {meeting.clientName}
                          </CardTitle>
                          <CardDescription className="mt-1">
                            {meeting.propertyTitle || "General Consultation"}
                          </CardDescription>
                        </div>
                        <Badge className={getStatusColor(meeting.status)} variant="outline">
                          {meeting.status}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-3">
                          <div className="flex items-center text-sm">
                            <Calendar className="h-4 w-4 mr-2 text-muted-foreground" />
                            <span className="font-medium">{formatDate(meeting.meetingDate)}</span>
                          </div>
                          <div className="flex items-center text-sm">
                            <Clock className="h-4 w-4 mr-2 text-muted-foreground" />
                            <span>{formatTime(meeting.meetingTime)}</span>
                          </div>
                          <div className="flex items-start text-sm">
                            <MapPin className="h-4 w-4 mr-2 mt-0.5 text-muted-foreground flex-shrink-0" />
                            <div>
                              <div className="font-medium">{meeting.officeName}</div>
                              <div className="text-muted-foreground">{meeting.officeAddress}</div>
                            </div>
                          </div>
                        </div>
                        <div className="space-y-3">
                          <div className="flex items-center text-sm">
                            <Phone className="h-4 w-4 mr-2 text-muted-foreground" />
                            <span>{meeting.clientPhone}</span>
                          </div>
                          <div className="flex items-center text-sm">
                            <Mail className="h-4 w-4 mr-2 text-muted-foreground" />
                            <span>{meeting.clientEmail}</span>
                          </div>
                          {meeting.propertyAddress && (
                            <div className="flex items-start text-sm">
                              <Building2 className="h-4 w-4 mr-2 mt-0.5 text-muted-foreground flex-shrink-0" />
                              <span className="text-muted-foreground">{meeting.propertyAddress}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {meeting.notes && (
                        <div className="pt-3 border-t">
                          <h4 className="font-medium text-sm mb-1">Notes</h4>
                          <p className="text-sm text-muted-foreground">{meeting.notes}</p>
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-3 border-t">
                        <span className="text-xs text-muted-foreground">
                          Created: {new Date(meeting.createdAt).toLocaleDateString()}
                        </span>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline">
                            Edit
                          </Button>
                          <Button size="sm" variant="outline">
                            Reschedule
                          </Button>
                          {meeting.status === "scheduled" && <Button size="sm">Mark Complete</Button>}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </TabsContent>

              <TabsContent value="calendar" className="space-y-6">
                {Object.keys(meetingsByDate).length > 0 ? (
                  <div className="space-y-6">
                    {Object.entries(meetingsByDate).map(([date, meetings]) => (
                      <Card key={date}>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Calendar className="h-5 w-5 text-primary" />
                            {formatDate(date)}
                          </CardTitle>
                          <CardDescription>{meetings.length} meeting(s) scheduled</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {meetings.map((meeting) => (
                              <div
                                key={meeting.id}
                                className="flex items-center justify-between p-3 bg-muted rounded-lg"
                              >
                                <div className="flex items-center space-x-3">
                                  <div className="text-sm font-medium">{formatTime(meeting.meetingTime)}</div>
                                  <div className="text-sm">
                                    <span className="font-medium">{meeting.clientName}</span>
                                    {meeting.propertyTitle && (
                                      <span className="text-muted-foreground"> - {meeting.propertyTitle}</span>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge className={getStatusColor(meeting.status)} variant="outline">
                                    {meeting.status}
                                  </Badge>
                                  <Button size="sm" variant="outline">
                                    View
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No meetings found for the selected criteria.</p>
                  </div>
                )}
              </TabsContent>
            </Tabs>

            {filteredMeetings.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No meetings found matching your criteria.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
