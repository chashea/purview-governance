using '../main.bicep'

param environmentName = 'dev'
param location = 'eastus'
param allowedTenantIds = '' // Comma-separated GCC tenant GUIDs, e.g. 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy'
param openAiDeploymentModel = 'gpt-4o'
param deployerObjectId = '' // Entra ID object ID of the deploying user/service principal — run: az ad signed-in-user show --query id -o tsv
param grafanaAdminGroupId = '' // Entra ID group object ID for Grafana Admins (optional)
param grafanaEditorGroupId = '' // Entra ID group object ID for Grafana Editors (optional)
param grafanaViewerGroupId = '' // Entra ID group object ID for Grafana Viewers (optional)
