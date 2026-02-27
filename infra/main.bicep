// ──────────────────────────────────────────────────────────────────
// Purview Governance — Azure Commercial Infrastructure
//
// Deploys: Storage, Function App, Key Vault, OpenAI, Monitoring,
//          Managed Grafana, Networking (private endpoints)
//
// Usage:
//   az deployment group create \
//     --resource-group rg-purview-governance \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/prod.bicepparam
// ──────────────────────────────────────────────────────────────────

targetScope = 'resourceGroup'

@allowed(['dev', 'prod'])
param environmentName string = 'prod'

param location string = resourceGroup().location

@description('Comma-separated list of allowed tenant GUIDs for ingestion')
param allowedTenantIds string = ''

@description('Comma-separated list of allowed certificate thumbprints')
param allowedCertThumbprints string = ''

@description('Azure OpenAI model deployment name')
param openAiDeploymentModel string = 'gpt-4o'

@description('Object ID of the deployer for Key Vault access policies')
param deployerObjectId string = ''

@description('Entra ID group object IDs for Grafana RBAC')
param grafanaAdminGroupId string = ''
param grafanaEditorGroupId string = ''
param grafanaViewerGroupId string = ''

var prefix = 'pvgov'
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageName = '${prefix}stor${uniqueSuffix}'
var functionAppName = '${prefix}-func-${environmentName}'
var keyVaultName = '${prefix}-kv-${uniqueSuffix}'
var openAiName = '${prefix}-oai-${uniqueSuffix}'
var appInsightsName = '${prefix}-ai-${environmentName}'
var logAnalyticsName = '${prefix}-la-${environmentName}'
var appServicePlanName = '${prefix}-asp-${environmentName}'
var grafanaName = '${prefix}-grafana-${environmentName}'

// ── Storage Account + Tables ────────────────────────────────────

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    storageAccountName: storageName
    location: location
  }
}

// ── Key Vault ───────────────────────────────────────────────────

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    keyVaultName: keyVaultName
    location: location
    deployerObjectId: deployerObjectId
  }
}

// ── Monitoring (Log Analytics + App Insights) ───────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    location: location
  }
}

// ── Azure OpenAI ────────────────────────────────────────────────

module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    openAiName: openAiName
    location: location
    deploymentModel: openAiDeploymentModel
  }
}

// ── Function App ────────────────────────────────────────────────

module functionApp 'modules/function-app.bicep' = {
  name: 'functionApp'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: location
    storageAccountName: storage.outputs.storageAccountName
    storageAccountId: storage.outputs.storageAccountId
    appInsightsInstrumentationKey: monitoring.outputs.appInsightsInstrumentationKey
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: keyVault.outputs.keyVaultUri
    openAiEndpoint: openai.outputs.openAiEndpoint
    openAiDeployment: openAiDeploymentModel
    allowedTenantIds: allowedTenantIds
    allowedCertThumbprints: allowedCertThumbprints
  }
}

// ── Grafana ─────────────────────────────────────────────────────

module grafana 'modules/grafana.bicep' = {
  name: 'grafana'
  params: {
    grafanaName: grafanaName
    location: location
    adminGroupId: grafanaAdminGroupId
    editorGroupId: grafanaEditorGroupId
    viewerGroupId: grafanaViewerGroupId
  }
}

// ── RBAC: Function App Managed Identity → Storage, Key Vault, OpenAI

// Storage Table Data Contributor
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.outputs.storageAccountId, functionApp.outputs.functionAppPrincipalId, '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3') // Storage Table Data Contributor
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.keyVaultId, functionApp.outputs.functionAppPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User
resource oaiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openai.outputs.openAiId, functionApp.outputs.functionAppPrincipalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ─────────────────────────────────────────────────────

output storageAccountName string = storage.outputs.storageAccountName
output functionAppUrl string = functionApp.outputs.functionAppUrl
output functionAppName string = functionAppName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output openAiEndpoint string = openai.outputs.openAiEndpoint
output grafanaUrl string = grafana.outputs.grafanaUrl
output appInsightsName string = appInsightsName
