
// File: policydefinition_DINE-PGFlex-LogDiscon.bicep
@description('Deploy if not exists, turn on PostgreSQL Log_Disconnections')
var policyDefinitionName = 'DINE-PGFlexLogDiscon'

@description('Friendly name')
var policyDisplayName = 'DINE-PostgresSQLFlexLogDiscon'

@description('Description')
var policyDescription = 'Deploy if not exists, turn on PostgreSQL log_disconnections.'

var evaluationDelay = 'PT1M'

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
      listOfAllowedEnvironment: {
        type: 'Array'
        metadata: {
          displayName: 'List of Allowed environments'
          description: 'Where the policy will be active.'
        }
        defaultValue: [
          'Dev'
          'DEV'
        ]
      }
    }
    policyRule: {
      if: {
        allOf: [
          { field: 'type', equals: 'Microsoft.DBforPostgreSQL/flexibleServers' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/state', equals: 'Ready' },
          { field: "tags['opEnvironment']", in: "[parameters('listOfAllowedEnvironment')]" }
        ]
      }
      then: {
        effect: "[parameters('effect')]"
        details: {
          type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
          name: 'log_disconnections'
          existenceCondition: {
            field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/value'
            equals: 'on'
          }
          deployment: {
            properties: {
              mode: 'incremental'
              parameters: {
                fullName: {
                  type: 'string'
                  defaultValue: "[field('fullName')]"
                }
              }
              template: {
                $schema: 'https://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#'
                contentVersion: '1.0.0.0'
                resources: [
                  {
                    name: "[concat(parameters('fullName'), '/log_disconnections')]",
                    type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations',
                    apiVersion: '2022-01-20-preview',
                    properties: {
                      value: 'on',
                      source: 'user-override'
                    }
                  }
                ]
              }
            }
          }
          roleDefinitionIds: [
            '/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c'
          ]
        }
      }
    }
    evaluationDelay: evaluationDelay
  }
}
