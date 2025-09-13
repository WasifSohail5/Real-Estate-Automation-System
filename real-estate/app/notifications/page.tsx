"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Navigation } from "@/components/navigation"
import { Search, Mail, Bell, Send, Archive, Settings, Clock, User, Building2 } from "lucide-react"

// Mock email and notification data
const mockEmails = [
  {
    id: 1,
    type: "property_match",
    subject: "New Property Match: Modern Downtown Condo",
    recipient: "sarah.johnson@email.com",
    clientName: "Sarah Johnson",
    propertyTitle: "Modern Downtown Condo",
    status: "sent",
    timestamp: "2024-01-15T10:30:00Z",
    content: "We found a perfect match for your preferences! This modern downtown condo features...",
  },
  {
    id: 2,
    type: "meeting_confirmation",
    subject: "Meeting Confirmation - Property Viewing",
    recipient: "m.chen@email.com",
    clientName: "Michael Chen",
    propertyTitle: "Luxury Bellevue Estate",
    status: "delivered",
    timestamp: "2024-01-15T09:15:00Z",
    content: "Your property viewing appointment has been confirmed for tomorrow at 2:00 PM...",
  },
  {
    id: 3,
    type: "follow_up",
    subject: "Following up on your property search",
    recipient: "emily.r@email.com",
    clientName: "Emily Rodriguez",
    propertyTitle: null,
    status: "opened",
    timestamp: "2024-01-14T16:45:00Z",
    content: "Hi Emily, I wanted to follow up on your recent property inquiries...",
  },
  {
    id: 4,
    type: "property_match",
    subject: "3 New Properties Match Your Criteria",
    recipient: "d.thompson@email.com",
    clientName: "David Thompson",
    propertyTitle: "Family Home in Fremont",
    status: "sent",
    timestamp: "2024-01-14T14:20:00Z",
    content: "Great news! We've found 3 new properties that match your search criteria...",
  },
]

const mockNotifications = [
  {
    id: 1,
    type: "system",
    title: "Property Matching System Started",
    message: "The automated property matching system has been started successfully.",
    timestamp: "2024-01-15T11:00:00Z",
    read: false,
    priority: "info",
  },
  {
    id: 2,
    type: "match",
    title: "New Property Match Found",
    message: "Found 2 new property matches for Sarah Johnson based on her preferences.",
    timestamp: "2024-01-15T10:30:00Z",
    read: false,
    priority: "high",
  },
  {
    id: 3,
    type: "email",
    title: "Email Delivery Confirmed",
    message: "Property match email successfully delivered to m.chen@email.com",
    timestamp: "2024-01-15T09:15:00Z",
    read: true,
    priority: "low",
  },
  {
    id: 4,
    type: "meeting",
    title: "Meeting Scheduled",
    message: "New property viewing meeting scheduled for Michael Chen on Jan 16, 2:00 PM",
    timestamp: "2024-01-14T17:30:00Z",
    read: true,
    priority: "medium",
  },
]

export default function NotificationsPage() {
  const [searchTerm, setSearchTerm] = useState("")
  const [emailFilter, setEmailFilter] = useState("all")
  const [notificationFilter, setNotificationFilter] = useState("all")

  const filteredEmails = useMemo(() => {
    return mockEmails.filter((email) => {
      const matchesSearch =
        email.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
        email.clientName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        email.recipient.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesFilter = emailFilter === "all" || email.status === emailFilter
      return matchesSearch && matchesFilter
    })
  }, [searchTerm, emailFilter])

  const filteredNotifications = useMemo(() => {
    return mockNotifications.filter((notification) => {
      const matchesSearch =
        notification.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        notification.message.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesFilter =
        notificationFilter === "all" ||
        (notificationFilter === "unread" && !notification.read) ||
        (notificationFilter === "read" && notification.read)
      return matchesSearch && matchesFilter
    })
  }, [searchTerm, notificationFilter])

  const getEmailStatusColor = (status: string) => {
    switch (status) {
      case "sent":
        return "bg-blue-100 text-blue-800 border-blue-200"
      case "delivered":
        return "bg-green-100 text-green-800 border-green-200"
      case "opened":
        return "bg-purple-100 text-purple-800 border-purple-200"
      case "failed":
        return "bg-red-100 text-red-800 border-red-200"
      default:
        return "bg-gray-100 text-gray-800 border-gray-200"
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "bg-red-100 text-red-800 border-red-200"
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-200"
      case "low":
        return "bg-green-100 text-green-800 border-green-200"
      default:
        return "bg-gray-100 text-gray-800 border-gray-200"
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "property_match":
        return <Building2 className="h-4 w-4" />
      case "meeting_confirmation":
        return <Clock className="h-4 w-4" />
      case "follow_up":
        return <User className="h-4 w-4" />
      case "system":
        return <Settings className="h-4 w-4" />
      case "match":
        return <Building2 className="h-4 w-4" />
      case "email":
        return <Mail className="h-4 w-4" />
      case "meeting":
        return <Clock className="h-4 w-4" />
      default:
        return <Bell className="h-4 w-4" />
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="lg:pl-64">
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold text-foreground">Email & Notifications</h1>
                <p className="text-muted-foreground mt-2">Monitor email communications and system notifications</p>
              </div>
              <Button className="mt-4 sm:mt-0">
                <Send className="h-4 w-4 mr-2" />
                Compose Email
              </Button>
            </div>

            <Tabs defaultValue="emails" className="space-y-6">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="emails" className="flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  Email Communications
                </TabsTrigger>
                <TabsTrigger value="notifications" className="flex items-center gap-2">
                  <Bell className="h-4 w-4" />
                  System Notifications
                </TabsTrigger>
              </TabsList>

              <TabsContent value="emails" className="space-y-6">
                {/* Email Search and Filter */}
                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                    <Input
                      placeholder="Search emails by subject, client, or recipient..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant={emailFilter === "all" ? "default" : "outline"}
                      onClick={() => setEmailFilter("all")}
                      size="sm"
                    >
                      All
                    </Button>
                    <Button
                      variant={emailFilter === "sent" ? "default" : "outline"}
                      onClick={() => setEmailFilter("sent")}
                      size="sm"
                    >
                      Sent
                    </Button>
                    <Button
                      variant={emailFilter === "delivered" ? "default" : "outline"}
                      onClick={() => setEmailFilter("delivered")}
                      size="sm"
                    >
                      Delivered
                    </Button>
                    <Button
                      variant={emailFilter === "opened" ? "default" : "outline"}
                      onClick={() => setEmailFilter("opened")}
                      size="sm"
                    >
                      Opened
                    </Button>
                  </div>
                </div>

                {/* Email List */}
                <div className="space-y-4">
                  {filteredEmails.map((email) => (
                    <Card key={email.id} className="hover:shadow-md transition-shadow">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start space-x-3 flex-1">
                            <div className="p-2 bg-muted rounded-lg">{getTypeIcon(email.type)}</div>
                            <div className="flex-1 min-w-0">
                              <CardTitle className="text-lg line-clamp-1">{email.subject}</CardTitle>
                              <CardDescription className="flex items-center gap-2 mt-1">
                                <span>To: {email.clientName}</span>
                                <span className="text-muted-foreground">({email.recipient})</span>
                              </CardDescription>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge className={getEmailStatusColor(email.status)} variant="outline">
                              {email.status}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              {new Date(email.timestamp).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{email.content}</p>
                        {email.propertyTitle && (
                          <div className="flex items-center gap-2 mb-3">
                            <Building2 className="h-3 w-3 text-muted-foreground" />
                            <span className="text-sm text-muted-foreground">
                              Related Property: {email.propertyTitle}
                            </span>
                          </div>
                        )}
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">
                            {new Date(email.timestamp).toLocaleString()}
                          </span>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline">
                              View Details
                            </Button>
                            <Button size="sm" variant="outline">
                              <Archive className="h-3 w-3 mr-1" />
                              Archive
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="notifications" className="space-y-6">
                {/* Notification Search and Filter */}
                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                    <Input
                      placeholder="Search notifications..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant={notificationFilter === "all" ? "default" : "outline"}
                      onClick={() => setNotificationFilter("all")}
                      size="sm"
                    >
                      All
                    </Button>
                    <Button
                      variant={notificationFilter === "unread" ? "default" : "outline"}
                      onClick={() => setNotificationFilter("unread")}
                      size="sm"
                    >
                      Unread
                    </Button>
                    <Button
                      variant={notificationFilter === "read" ? "default" : "outline"}
                      onClick={() => setNotificationFilter("read")}
                      size="sm"
                    >
                      Read
                    </Button>
                  </div>
                </div>

                {/* Notifications List */}
                <div className="space-y-3">
                  {filteredNotifications.map((notification) => (
                    <Card
                      key={notification.id}
                      className={`hover:shadow-md transition-shadow ${!notification.read ? "border-l-4 border-l-primary" : ""}`}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start space-x-3 flex-1">
                            <div className="p-2 bg-muted rounded-lg">{getTypeIcon(notification.type)}</div>
                            <div className="flex-1 min-w-0">
                              <h4 className={`font-medium ${!notification.read ? "font-semibold" : ""}`}>
                                {notification.title}
                              </h4>
                              <p className="text-sm text-muted-foreground mt-1">{notification.message}</p>
                              <span className="text-xs text-muted-foreground">
                                {new Date(notification.timestamp).toLocaleString()}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge className={getPriorityColor(notification.priority)} variant="outline">
                              {notification.priority}
                            </Badge>
                            {!notification.read && <div className="w-2 h-2 bg-primary rounded-full" />}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>
            </Tabs>

            {(filteredEmails.length === 0 || filteredNotifications.length === 0) && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No items found matching your criteria.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
