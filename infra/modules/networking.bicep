// Private Endpoints (optional — enable for production lockdown)
//
// This module creates private endpoints for Storage, Key Vault, and OpenAI
// so that the Function App communicates over the Azure backbone, not public internet.
//
// To use: pass resource IDs and a VNet/subnet for private endpoint placement.

param location string
param vnetName string = ''
param subnetName string = 'private-endpoints'
param storageAccountId string = ''
param keyVaultId string = ''
param openAiId string = ''

// Only deploy if a VNet name is provided
var deployPrivateEndpoints = !empty(vnetName)

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' existing = if (deployPrivateEndpoints) {
  name: vnetName
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-05-01' existing = if (deployPrivateEndpoints) {
  parent: vnet
  name: subnetName
}

// Storage Table private endpoint
resource storagePe 'Microsoft.Network/privateEndpoints@2023-05-01' = if (deployPrivateEndpoints && !empty(storageAccountId)) {
  name: 'pe-storage-table'
  location: location
  properties: {
    subnet: { id: subnet.id }
    privateLinkServiceConnections: [
      {
        name: 'storage-table'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: ['table']
        }
      }
    ]
  }
}

// Key Vault private endpoint
resource kvPe 'Microsoft.Network/privateEndpoints@2023-05-01' = if (deployPrivateEndpoints && !empty(keyVaultId)) {
  name: 'pe-keyvault'
  location: location
  properties: {
    subnet: { id: subnet.id }
    privateLinkServiceConnections: [
      {
        name: 'keyvault'
        properties: {
          privateLinkServiceId: keyVaultId
          groupIds: ['vault']
        }
      }
    ]
  }
}

// OpenAI private endpoint
resource oaiPe 'Microsoft.Network/privateEndpoints@2023-05-01' = if (deployPrivateEndpoints && !empty(openAiId)) {
  name: 'pe-openai'
  location: location
  properties: {
    subnet: { id: subnet.id }
    privateLinkServiceConnections: [
      {
        name: 'openai'
        properties: {
          privateLinkServiceId: openAiId
          groupIds: ['account']
        }
      }
    ]
  }
}
