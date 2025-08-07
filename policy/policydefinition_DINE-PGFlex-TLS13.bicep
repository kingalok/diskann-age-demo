// File: policydefinition_DINE-PGFlex-TLS13.bicep
@description('Deploy if not exists, enforce TLS1_3 for PostgreSQL Flexible Server')
var policyDefinitionName = 'DINE-PGFlexTLS13'

@description('Friendly name')
var policyDisplayName = 'DINE-PostgresSQLFlexTLS13'

@description('Description')
var policyDescription = 'Ensure PostgreSQL Flexible Server version 17 uses minimalTlsVersion TLS1_3.'

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
          { field: 'type', equals: 'Microsoft.DBforPostgreSQL/flexibleServers' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/version', equals: '17' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/minimalTlsVersion', notEquals: 'TLS1_3' }
        ]
      }
      then: {
        effect: "[parameters('effect')]"
        details: {
          type: 'Microsoft.DBforPostgreSQL/flexibleServers'
          name: 'minimalTlsVersion'
          existenceCondition: {
            field: 'Microsoft.DBforPostgreSQL/flexibleServers/minimalTlsVersion'
            equals: 'TLS1_3'
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
                    name: "[field('name')]"
                    type: 'Microsoft.DBforPostgreSQL/flexibleServers'
                    apiVersion: '2022-01-20-preview'
                    properties: {
                      minimalTlsVersion: 'TLS1_3'
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
