// File: policydefinition_DINE-PGFlex-SSLMinProtocol.bicep
@description('Deploy if not exists, enforce ssl_min_protocol_version = TLS1_3 on PostgreSQL Flexible Server')
var policyDefinitionName = 'DINE-PGFlexSSLMinProtocol'

@description('Friendly name')
var policyDisplayName = 'DINE-PostgresSQLFlexSSLMinProtocol'

@description('Description')
var policyDescription = 'Ensure PostgreSQL Flexible Server has ssl_min_protocol_version set to TLS1_3.'

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
      contact: 'nitin.potdar@ubs.com'
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
          displayName: 'List of Allowed environments where DINE policy will be active'
          description: 'Provide the list of allowed environments where the policy will be active.'
        }
        defaultValue: [
          'DEV'
          'UAT'
          'PROD'
        ]
      }
    }
    policyRule: {
      if: {
        allOf: [
          { field: 'type', equals: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations' },
          { field: 'name', equals: 'ssl_min_protocol_version' },
          { field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/value', notEquals: 'TLS1_3' },
          { field: "tags['opEnvironment']", in: "[parameters('listOfAllowedEnvironment')]" }
        ]
      }
      then: {
        effect: "[parameters('effect')]"
        details: {
          type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
          name: 'ssl_min_protocol_version'
          existenceCondition: {
            field: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations/value'
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
                parameters: {
                  fullName: {
                    type: 'string'
                    defaultValue: "[field('fullName')]"
                  }
                }
                resources: [
                  {
                    name: "[concat(parameters('fullName'), '/ssl_min_protocol_version')]"
                    type: 'Microsoft.DBforPostgreSQL/flexibleServers/configurations'
                    apiVersion: '2022-01-20-preview'
                    properties: {
                      value: 'TLS1_3'
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