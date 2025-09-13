"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Navigation } from "@/components/navigation"
import { Search, MapPin, Bed, Bath, Square, Plus, Eye } from "lucide-react"

// Mock property data - replace with API call when backend endpoints are available
const mockProperties = [
  {
    id: 1,
    title: "Modern Downtown Condo",
    address: "123 Pine St, Seattle, WA 98101",
    price: 950000,
    bedrooms: 2,
    bathrooms: 2,
    sqft: 1200,
    type: "Condo",
    status: "Available",
    description: "Stunning modern condo with city views, high-end finishes, and premium amenities.",
    features: ["City View", "Parking", "Gym", "Concierge"],
    listingDate: "2024-01-10",
    image: "/modern-downtown-condo-interior.jpg",
  },
  {
    id: 2,
    title: "Luxury Bellevue Estate",
    address: "456 Bellevue Way, Bellevue, WA 98004",
    price: 1750000,
    bedrooms: 4,
    bathrooms: 3,
    sqft: 3200,
    type: "House",
    status: "Available",
    description: "Elegant estate home with premium finishes, gourmet kitchen, and private garden.",
    features: ["Garden", "Gourmet Kitchen", "Fireplace", "3-Car Garage"],
    listingDate: "2024-01-08",
    image: "/luxury-estate-home-exterior.jpg",
  },
  {
    id: 3,
    title: "Historic Capitol Hill Townhouse",
    address: "789 Broadway, Seattle, WA 98102",
    price: 825000,
    bedrooms: 3,
    bathrooms: 2,
    sqft: 1800,
    type: "Townhouse",
    status: "Pending",
    description: "Charming historic townhouse with original details and modern updates.",
    features: ["Historic Charm", "Updated Kitchen", "Hardwood Floors", "Rooftop Deck"],
    listingDate: "2024-01-05",
    image: "/historic-townhouse-brick-exterior.jpg",
  },
  {
    id: 4,
    title: "Family Home in Fremont",
    address: "321 Fremont Ave, Seattle, WA 98103",
    price: 875000,
    bedrooms: 4,
    bathrooms: 2,
    sqft: 2400,
    type: "House",
    status: "Available",
    description: "Perfect family home with large yard, updated kitchen, and quiet neighborhood.",
    features: ["Large Yard", "Updated Kitchen", "Quiet Street", "Near Schools"],
    listingDate: "2024-01-12",
    image: "/family-house-with-yard.jpg",
  },
]

export default function PropertiesPage() {
  const [searchTerm, setSearchTerm] = useState("")
  const [typeFilter, setTypeFilter] = useState("All")
  const [statusFilter, setStatusFilter] = useState("All")

  const filteredProperties = useMemo(() => {
    return mockProperties.filter((property) => {
      const matchesSearch =
        property.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        property.address.toLowerCase().includes(searchTerm.toLowerCase()) ||
        property.description.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesType = typeFilter === "All" || property.type === typeFilter
      const matchesStatus = statusFilter === "All" || property.status === statusFilter
      return matchesSearch && matchesType && matchesStatus
    })
  }, [searchTerm, typeFilter, statusFilter])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "Available":
        return "bg-green-100 text-green-800 border-green-200"
      case "Pending":
        return "bg-yellow-100 text-yellow-800 border-yellow-200"
      case "Sold":
        return "bg-gray-100 text-gray-800 border-gray-200"
      default:
        return "bg-gray-100 text-gray-800 border-gray-200"
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(price)
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="lg:pl-64">
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold text-foreground">Properties</h1>
                <p className="text-muted-foreground mt-2">Browse and manage property listings</p>
              </div>
              <Button className="mt-4 sm:mt-0">
                <Plus className="h-4 w-4 mr-2" />
                Add New Property
              </Button>
            </div>

            {/* Search and Filter Controls */}
            <div className="flex flex-col lg:flex-row gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search properties by title, address, or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <div className="flex gap-1">
                  <Button
                    variant={typeFilter === "All" ? "default" : "outline"}
                    onClick={() => setTypeFilter("All")}
                    size="sm"
                  >
                    All Types
                  </Button>
                  <Button
                    variant={typeFilter === "House" ? "default" : "outline"}
                    onClick={() => setTypeFilter("House")}
                    size="sm"
                  >
                    Houses
                  </Button>
                  <Button
                    variant={typeFilter === "Condo" ? "default" : "outline"}
                    onClick={() => setTypeFilter("Condo")}
                    size="sm"
                  >
                    Condos
                  </Button>
                  <Button
                    variant={typeFilter === "Townhouse" ? "default" : "outline"}
                    onClick={() => setTypeFilter("Townhouse")}
                    size="sm"
                  >
                    Townhouses
                  </Button>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant={statusFilter === "All" ? "default" : "outline"}
                    onClick={() => setStatusFilter("All")}
                    size="sm"
                  >
                    All Status
                  </Button>
                  <Button
                    variant={statusFilter === "Available" ? "default" : "outline"}
                    onClick={() => setStatusFilter("Available")}
                    size="sm"
                  >
                    Available
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
            </div>

            {/* Properties Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredProperties.map((property) => (
                <Card key={property.id} className="hover:shadow-lg transition-shadow overflow-hidden">
                  <div className="relative">
                    <img
                      src={property.image || "/placeholder.svg"}
                      alt={property.title}
                      className="w-full h-48 object-cover"
                    />
                    <Badge className={`absolute top-3 right-3 ${getStatusColor(property.status)}`} variant="outline">
                      {property.status}
                    </Badge>
                  </div>

                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg line-clamp-1">{property.title}</CardTitle>
                        <CardDescription className="flex items-center mt-1">
                          <MapPin className="h-3 w-3 mr-1 flex-shrink-0" />
                          <span className="line-clamp-1">{property.address}</span>
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-2xl font-bold text-primary">{formatPrice(property.price)}</span>
                      <Badge variant="secondary">{property.type}</Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <div className="flex items-center">
                        <Bed className="h-4 w-4 mr-1" />
                        {property.bedrooms} bed
                      </div>
                      <div className="flex items-center">
                        <Bath className="h-4 w-4 mr-1" />
                        {property.bathrooms} bath
                      </div>
                      <div className="flex items-center">
                        <Square className="h-4 w-4 mr-1" />
                        {property.sqft.toLocaleString()} sqft
                      </div>
                    </div>

                    <p className="text-sm text-muted-foreground line-clamp-2">{property.description}</p>

                    <div className="flex flex-wrap gap-1">
                      {property.features.slice(0, 3).map((feature, index) => (
                        <Badge key={index} variant="outline" className="text-xs">
                          {feature}
                        </Badge>
                      ))}
                      {property.features.length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{property.features.length - 3} more
                        </Badge>
                      )}
                    </div>

                    <div className="flex gap-2 pt-2">
                      <Button size="sm" variant="outline" className="flex-1 bg-transparent">
                        <Eye className="h-3 w-3 mr-1" />
                        View Details
                      </Button>
                      <Button size="sm" className="flex-1">
                        Contact Agent
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {filteredProperties.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No properties found matching your criteria.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
