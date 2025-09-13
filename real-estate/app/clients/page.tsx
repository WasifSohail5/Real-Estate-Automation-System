"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Navigation } from "@/components/navigation"
import { Search, Phone, Mail, MapPin, Calendar, Plus } from "lucide-react"

// Mock client data - replace with API call when backend endpoints are available
const mockClients = [
  {
    id: 1,
    name: "Sarah Johnson",
    email: "sarah.johnson@email.com",
    phone: "(555) 123-4567",
    location: "Downtown Seattle",
    budget: "$800,000 - $1,200,000",
    preferences: "3+ bedrooms, Modern style, Near schools",
    status: "Active",
    lastContact: "2024-01-15",
    matchedProperties: 3,
  },
  {
    id: 2,
    name: "Michael Chen",
    email: "m.chen@email.com",
    phone: "(555) 234-5678",
    location: "Bellevue",
    budget: "$1,500,000 - $2,000,000",
    preferences: "Luxury condo, City view, Parking",
    status: "Active",
    lastContact: "2024-01-14",
    matchedProperties: 5,
  },
  {
    id: 3,
    name: "Emily Rodriguez",
    email: "emily.r@email.com",
    phone: "(555) 345-6789",
    location: "Capitol Hill",
    budget: "$600,000 - $900,000",
    preferences: "Historic charm, Walkable, Pet-friendly",
    status: "Pending",
    lastContact: "2024-01-12",
    matchedProperties: 2,
  },
  {
    id: 4,
    name: "David Thompson",
    email: "d.thompson@email.com",
    phone: "(555) 456-7890",
    location: "Fremont",
    budget: "$700,000 - $1,100,000",
    preferences: "Family home, Garden, Quiet neighborhood",
    status: "Active",
    lastContact: "2024-01-13",
    matchedProperties: 4,
  },
]

export default function ClientsPage() {
  const [searchTerm, setSearchTerm] = useState("")
  const [statusFilter, setStatusFilter] = useState("All")

  const filteredClients = useMemo(() => {
    return mockClients.filter((client) => {
      const matchesSearch =
        client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        client.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        client.location.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesStatus = statusFilter === "All" || client.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [searchTerm, statusFilter])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "Active":
        return "bg-green-100 text-green-800 border-green-200"
      case "Pending":
        return "bg-yellow-100 text-yellow-800 border-yellow-200"
      case "Inactive":
        return "bg-gray-100 text-gray-800 border-gray-200"
      default:
        return "bg-gray-100 text-gray-800 border-gray-200"
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
                <h1 className="text-3xl font-bold text-foreground">Clients</h1>
                <p className="text-muted-foreground mt-2">Manage your client relationships and preferences</p>
              </div>
              <Button className="mt-4 sm:mt-0">
                <Plus className="h-4 w-4 mr-2" />
                Add New Client
              </Button>
            </div>

            {/* Search and Filter Controls */}
            <div className="flex flex-col sm:flex-row gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search clients by name, email, or location..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  variant={statusFilter === "All" ? "default" : "outline"}
                  onClick={() => setStatusFilter("All")}
                  size="sm"
                >
                  All
                </Button>
                <Button
                  variant={statusFilter === "Active" ? "default" : "outline"}
                  onClick={() => setStatusFilter("Active")}
                  size="sm"
                >
                  Active
                </Button>
                <Button
                  variant={statusFilter === "Pending" ? "default" : "outline"}
                  onClick={() => setStatusFilter("Pending")}
                  size="sm"
                >
                  Pending
                </Button>
              </div>
            </div>

            {/* Client Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredClients.map((client) => (
                <Card key={client.id} className="hover:shadow-lg transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{client.name}</CardTitle>
                        <CardDescription className="flex items-center mt-1">
                          <MapPin className="h-3 w-3 mr-1" />
                          {client.location}
                        </CardDescription>
                      </div>
                      <Badge className={getStatusColor(client.status)} variant="outline">
                        {client.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center text-sm text-muted-foreground">
                        <Mail className="h-3 w-3 mr-2" />
                        {client.email}
                      </div>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <Phone className="h-3 w-3 mr-2" />
                        {client.phone}
                      </div>
                    </div>

                    <div>
                      <h4 className="font-medium text-sm mb-1">Budget Range</h4>
                      <p className="text-sm text-muted-foreground">{client.budget}</p>
                    </div>

                    <div>
                      <h4 className="font-medium text-sm mb-1">Preferences</h4>
                      <p className="text-sm text-muted-foreground line-clamp-2">{client.preferences}</p>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t">
                      <div className="text-sm text-muted-foreground">
                        <Calendar className="h-3 w-3 inline mr-1" />
                        Last contact: {new Date(client.lastContact).toLocaleDateString()}
                      </div>
                      <Badge variant="secondary">{client.matchedProperties} matches</Badge>
                    </div>

                    <div className="flex gap-2 pt-2">
                      <Button size="sm" variant="outline" className="flex-1 bg-transparent">
                        View Details
                      </Button>
                      <Button size="sm" className="flex-1">
                        Contact
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {filteredClients.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No clients found matching your criteria.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
