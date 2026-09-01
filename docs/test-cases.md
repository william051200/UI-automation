# Test cases

Directory of the declarative scenarios under [`test_cases/`](../test_cases), consumed by `run_test.py`. Active test cases use the `<type>-<ID>-<description>.csv` naming convention so cases of the same type stay grouped in directory listings.

## Active test cases

| Type | ID | Test case | Purpose |
|---|---:|---|---|
| E2E | 1 | [`e2e-1-verify_dotnet_info.csv`](../test_cases/e2e-1-verify_dotnet_info.csv) | Runs `dotnet --info`, archives its output as text and an image, and verifies that every installed SDK and runtime uses a stable `major.minor.patch` version. |
| E2E | 3 | [`e2e-3-template-test.csv`](../test_cases/e2e-3-template-test.csv) | Verifies the latest .NET framework offered by the Visual Studio Insiders MAUI and Console App project wizards, then builds and runs the console app. |
| Productivity | 1 | [`prod-1-cs_console_app.csv`](../test_cases/prod-1-cs_console_app.csv) | Creates a C# Console App in Visual Studio, validates its project settings, applies code changes with Hot Reload, and verifies the updated output. |
| Productivity | 2 | [`prod-2-hot_reload.csv`](../test_cases/prod-2-hot_reload.csv) | Creates and runs a Razor Pages project, edits its page model and markup, applies Hot Reload, and verifies the updated browser content. |
| Productivity | 3 | [`prod-3-dotnet_core_cs.csv`](../test_cases/prod-3-dotnet_core_cs.csv) | Exercises C# console and class-library development in Visual Studio for every installed ASP.NET Core major version, including editing, debugging, navigation, packing, and publishing. |
| Productivity | 3 | [`prod-3-dotnet_core_vb.csv`](../test_cases/prod-3-dotnet_core_vb.csv) | Runs the Visual Basic variant of the .NET Core scenario for every installed ASP.NET Core major version. |
| Productivity | 4 | [`prod-4-edit_file_dependencies.csv`](../test_cases/prod-4-edit_file_dependencies.csv) | Edits a C# project file in Visual Studio, manages target frameworks, package and project references, and compile items, then updates a NuGet package. |
| Productivity | 5 | [`prod-5-fsharp_xunit.csv`](../test_cases/prod-5-fsharp_xunit.csv) | Creates F# library and xUnit projects, runs passing and failing tests, debugs the failure, fixes it, and verifies both tests pass. |
| Productivity | 6 | [`prod-6-multi_project_build.csv`](../test_cases/prod-6-multi_project_build.csv) | Creates a multi-project F# solution, validates IntelliSense, rebuilds and debugs it, and inspects project properties. |

[`_template.csv`](../test_cases/_template.csv) is the authoring template and is not an executable catalog entry.

## Legacy `v0` test cases

These earlier scenarios remain available under [`test_cases/v0/`](../test_cases/v0) but do not use the active naming convention.

| Test case | Purpose |
|---|---|
| [`console_app.csv`](../test_cases/v0/console_app.csv) | Creates, configures, builds, and runs a C# Console App in Visual Studio. |
| [`dotnet_sdk_version.csv`](../test_cases/v0/dotnet_sdk_version.csv) | Validates installed .NET SDK and ASP.NET Core runtime versions, then builds and publishes a console app for each installed major version. |
| [`razor_breakpoint.csv`](../test_cases/v0/razor_breakpoint.csv) | Creates a Razor Pages project and exercises Visual Studio breakpoint and stepping behavior. |
| [`testcase1_console_nu1605.csv`](../test_cases/v0/testcase1_console_nu1605.csv) | Creates a C# Console App and edits its project file to reproduce and suppress NuGet warning NU1605. |
| [`vs_nuget.csv`](../test_cases/v0/vs_nuget.csv) | Creates a mixed C#/VB solution, installs and updates NuGet packages, and verifies the solution builds. |
