// Azure Function App (Python v2, Linux, Consumption)

param functionAppName string
param appServicePlanName string
param location string
param storageAccountName string
param storageAccountId string
param appInsightsInstrumentationKey string
param appInsightsConnectionString string
param keyVaultUri string
param openAiEndpoint string
param openAiDeployment string
param allowedTenantIds string
param allowedCertThumbprints string

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    clientCertEnabled: true
    clientCertMode: 'OptionalInteractiveUser'
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'PYTHON|3.11'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=core.windows.net;AccountKey=${listKeys(storageAccountId, '2023-01-01').keys[0].value}' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsightsInstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'STORAGE_ACCOUNT_NAME', value: storageAccountName }
        { name: 'KEY_VAULT_URL', value: keyVaultUri }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiDeployment }
        { name: 'AZURE_OPENAI_API_VERSION', value: '2024-08-01-preview' }
        { name: 'ALLOWED_TENANT_IDS', value: allowedTenantIds }
        { name: 'ALLOWED_CERT_THUMBPRINTS', value: allowedCertThumbprints }
      ]
    }
  }
}

output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppName string = functionApp.name
