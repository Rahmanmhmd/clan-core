{ lib, ... }:
let
  instanceOptions = lib.types.submodule {
    options.roles = lib.mkOption {
      description = ''
        Configuration for a service instance.

        Specific roles describe the membership of foreign machines.

        ```nix
        { # Configuration for an instance
          roles.<roleName>.machines = [ # List of machines ];
        }
        ```
      '';

      type = lib.types.attrsOf machinesList;
    };
  };

  machinesList = lib.types.submodule {
    options.machines = lib.mkOption {
      description = ''
        List of machines that are part of a role.

        ```nix
        { # Configuration for an instance
          roles.<roleName>.machines = [ # List of machines ];
        }
        ```
      '';
      type = lib.types.listOf lib.types.str;
    };
  };
in
{
  options.clan.inventory.services = lib.mkOption {
    default = { };
    description = ''
      Configuration for each inventory service.

      Each service can have multiple instances as follows:

      ```
      {serviceName}.{instancename} = { # Configuration for an instance }
      ```
    '';
    type = lib.types.attrsOf (lib.types.attrsOf instanceOptions);
  };
  options.clan.inventory.assertions = lib.mkOption {
    default = { };
    internal = true;
    visible = false;
    type = lib.types.attrsOf (
      # TODO: use NixOS upstream type
      lib.types.submodule {
        options = {
          assertion = lib.mkOption {
            type = lib.types.bool;
          };
          message = lib.mkOption {
            type = lib.types.str;
          };
        };
      }
    );
  };
}
