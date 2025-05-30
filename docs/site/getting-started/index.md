# :material-clock-fast: Getting Started

Ready to create your own clan and manage a fleet of machines? Follow these simple steps to get started.

By the end of this guide, you'll have a fresh NixOS configuration ready to push to one or more machines. You'll create a new git repository and a flake, and all you need is at least one machine to push to. This is the easiest way to begin, and we recommend you to copy your existing configuration into this new setup!


### Prerequisites

=== "**Linux**"

    Clan depends on nix installed on your system. Run the following command to install nix.

    ```bash
    curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
    ```

    If you already have installed Nix, make sure you have the `nix-command` and `flakes` configuration enabled in your ~/.config/nix/nix.conf.
    The determinate installer already comes with this configuration by default.

    ```bash
    # /etc/nix/nix.conf or ~/.config/nix/nix.conf
    experimental-features = nix-command flakes
    ```

=== "**NixOS**"

    If you run NixOS the `nix` binary is already installed.

    You will also need to enable the `flakes` and `nix-commands` experimental features in your configuration.nix:

    ```nix
    { nix.settings.experimental-features = [ "nix-command" "flakes" ]; }
    ```

=== "**Other**"

    Clan doesn't offer dedicated support for other operating systems yet.

### Step 1: Add Clan CLI to Your Shell

Add the Clan CLI into your development workflow:

```bash
nix shell git+https://git.clan.lol/clan/clan-core#clan-cli --refresh
```

You can find reference documentation for the `clan` cli program [here](../reference/cli/index.md).

Alternatively you can check out the help pages directly:
```terminalSession
clan --help
```

### Step 2: Initialize Your Project

If you want to migrate an existing project, follow this [guide](https://docs.clan.lol/manual/migration-guide/).

Set the foundation of your Clan project by initializing it as follows:

```bash
clan flakes create my-clan
```

This command creates the `flake.nix` and `.clan-flake` files for your project.
It will also generate files from a default template, to help show general clan usage patterns.

### Step 3: Verify the Project Structure

Ensure that all project files exist by running:

```bash
cd my-clan
tree
```

This should yield the following:

``` { .console .no-copy }
.
├── flake.nix
├── machines
│   ├── jon
│   │   ├── configuration.nix
│   │   └── hardware-configuration.nix
│   └── sara
│       ├── configuration.nix
│       └── hardware-configuration.nix
└── modules
    └── shared.nix

5 directories, 9 files
```

??? info "Recommended way of sourcing the `clan` cli tool"
    The default template also adds the `clan` cli tool to the development shell.
    Meaning you can get the exact version you need directly from the folder
    you are in right now.

    In the `my-clan` directory run the following command:
    ```
    nix develop
    ```
    That way you will have the tool available in the shell environment.
    We also recommend setting up [direnv](https://direnv.net/) for your shell, for a more convenient
    experience.
    
    

```bash
clan machines list
```

``` { .console .no-copy }
jon
sara
```

!!! success

    You just successfully bootstrapped your first clan directory.

