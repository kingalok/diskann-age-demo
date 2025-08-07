// File: policydefinition_DINE-PGFlex-LogCon.bicep
@description('Deploy if not exists, turn on PostgreSQL Log_Connections')
var policyDefinitionName = 'DINE-PGFlexLogCon'

@description('Friendly name')
var policyDisplayName = 'DINE-PostgresSQLFlexLogCon'

@description('Description')
var policyDescription = 'Deploy if not exists, turn on PostgreSQL log_connections.'

resource policyDefinition 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: policyDisplayName
    policyType: 'Custom'
    mode: 'Indexed'
    description: policyDescription
    metadata: {
      category: 'Database'
      version: '1.0.0'
      createdBy: 'UBS'
    }
    parameters: {
      effect: {
        type: 'String'
        metadata: {
          displayName: 'Effect'
          description: 'Enable or disable the execution of the policy'
        }
        allowedValues: [
          'auditIfNotExists'
          'deployIfNotExists'
          'disabled'
        ]
        defaultValue: 'deployIfNotExists'
      }
    }
    policyRule: {
      if: {
        allOf: [
          { field: 'type', equals: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/name', equals: 'log_connections' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/value', notEquals: 'on' }
        ]
      }
      then: {
        effect: "[parameters('effect')]"
        details: {
          type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
          name: 'log_connections'
          existenceCondition: {
            field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/value'
            equals: 'on'
          }
          roleDefinitionIds: [
            '/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c'
          ]
          deployment: {
            properties: {
              mode: 'incremental'
              template: {
                $schema: 'https://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#'
                contentVersion: '1.0.0.0'
                resources: [
                  {
                    name: "[concat(field('fullName'), '/log_connections')]"
                    type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
                    apiVersion: '2022-01-20-preview'
                    properties: {
                      value: 'on'
                      source: 'user-override'
                    }
                  }
                ]
              }
            }
          }
        }
      }
    }
  }
}
