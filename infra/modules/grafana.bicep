// Azure Managed Grafana with Entra ID SSO + RBAC

param grafanaName string
param location string

@description('Entra ID group object ID for Grafana Admin role')
param adminGroupId string = ''

@description('Entra ID group object ID for Grafana Editor role')
param editorGroupId string = ''

@description('Entra ID group object ID for Grafana Viewer role')
param viewerGroupId string = ''

resource grafana 'Microsoft.Dashboard/grafana@2023-09-01' = {
  name: grafanaName
  location: location
  sku: { name: 'Standard' }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    apiKey: 'Disabled'
    deterministicOutboundIP: 'Disabled'
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
    grafanaIntegrations: {
      azureMonitorWorkspaceIntegrations: []
    }
  }
}

// Grafana Admin role assignment (Entra ID group)
resource grafanaAdminRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminGroupId)) {
  name: guid(grafana.id, adminGroupId, '22926164-76b3-42b3-bc55-97df8dab3e41')
  scope: grafana
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '22926164-76b3-42b3-bc55-97df8dab3e41') // Grafana Admin
    principalId: adminGroupId
    principalType: 'Group'
  }
}

// Grafana Editor role assignment
resource grafanaEditorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(editorGroupId)) {
  name: guid(grafana.id, editorGroupId, 'a79a5197-3a5c-4973-a920-486035ffd60f')
  scope: grafana
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a79a5197-3a5c-4973-a920-486035ffd60f') // Grafana Editor
    principalId: editorGroupId
    principalType: 'Group'
  }
}

// Grafana Viewer role assignment
resource grafanaViewerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(viewerGroupId)) {
  name: guid(grafana.id, viewerGroupId, '60921a7e-fef1-4a43-9b16-a26c52ad4769')
  scope: grafana
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '60921a7e-fef1-4a43-9b16-a26c52ad4769') // Grafana Viewer
    principalId: viewerGroupId
    principalType: 'Group'
  }
}

output grafanaUrl string = grafana.properties.endpoint
output grafanaId string = grafana.id
output grafanaPrincipalId string = grafana.identity.principalId
