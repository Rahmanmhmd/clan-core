{
  lib ? import <nixpkgs/lib>,
  ...
}:
let

  inherit (lib)
    filterAttrs
    flatten
    mapAttrsToList
    ;
in
{

  collectFiles =
    vars:
    let
      relevantFiles =
        generator:
        filterAttrs (
          _name: f: f.secret && f.deploy && (f.neededFor == "users" || f.neededFor == "services")
        ) generator.files;
      allFiles = flatten (
        mapAttrsToList (
          gen_name: generator:
          mapAttrsToList (fname: file: {
            name = fname;
            generator = gen_name;
            neededForUsers = file.neededFor == "users";
            inherit (generator) share;
            inherit (file) owner group mode;
          }) (relevantFiles generator)
        ) vars.generators
      );
    in
    allFiles;
}
