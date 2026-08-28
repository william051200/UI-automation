# Edit Project File (C#/VB)

## Prerequisites

- Ensure that the **.NET desktop development** workload is installed for Visual Studio.
- Ensure that the **.NET Framework 4.8 SDK** and **.NET Framework 4.8 targeting pack** are installed.
- Ensure that the machine can restore the `Newtonsoft.Json` NuGet package.

## Test steps

1. Create two projects in one solution.

   1. Create a **C# Console App** project named `EditProjectConsole` in a solution named `EditProjectFile`.
   2. Target the console project to **.NET 9.0**.
   3. Add a **C# Class Library** project named `EditProjectLibrary` to the same solution.
   4. Target the class-library project to **.NET Standard 2.0**.

2. Edit the console project file.

   1. In **Solution Explorer**, right-click `EditProjectConsole` and select **Edit Project File**.
   2. Verify that `EditProjectConsole.csproj` opens in the editor.
   3. Change the project from a single target framework to multiple target frameworks by replacing:

      ```xml
      <TargetFramework>net9.0</TargetFramework>
      ```

      With:

      ```xml
      <TargetFrameworks>net9.0;net48</TargetFrameworks>
      ```

   4. Save the project file.
   5. Verify in **Solution Explorer** that `net9.0` and `net48` appear under `EditProjectConsole > Dependencies`.
   6. Add the following package reference and save the project file:

      ```xml
      <ItemGroup>
        <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />
      </ItemGroup>
      ```

   7. Verify that `Newtonsoft.Json (13.0.1)` appears under the console project's dependencies.
   8. Add the following project reference and save the project file:

      ```xml
      <ItemGroup>
        <ProjectReference Include="..\EditProjectLibrary\EditProjectLibrary.csproj" />
      </ItemGroup>
      ```

   9. Verify that `EditProjectLibrary` appears under the console project's project dependencies.
   10. Add a new class file named `Class1.cs` to `EditProjectConsole`.
   11. Add the following entry to exclude `Class1.cs`, and save the project file:

      ```xml
      <ItemGroup>
        <Compile Remove="Class1.cs" />
      </ItemGroup>
      ```

   12. Verify in **Solution Explorer** that `Class1.cs` is no longer displayed as a normal project item.

3. Verify and update the Dependencies Tree.

   1. In **Solution Explorer**, click **Show All Files**.
   2. Verify that the excluded `Class1.cs` is displayed.
   3. Right-click `Class1.cs` and select **Include In Project**.
   4. Verify that `Class1.cs` is included in the project and displayed as a normal project item.
   5. Under the console project's dependencies, select `Newtonsoft.Json (13.0.1)`.
   6. Verify that selecting the package updates the **Properties** window with information for `Newtonsoft.Json`.
   7. Right-click `Newtonsoft.Json (13.0.1)` and select **Update...**.
   8. Verify that the **NuGet: EditProjectConsole** tab opens.
   9. Update `Newtonsoft.Json` from version `13.0.1` to version `13.0.4`.
   10. Return to `EditProjectConsole.csproj` and verify that:

       ```xml
       <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />
       ```

       Has changed to:

       ```xml
       <PackageReference Include="Newtonsoft.Json" Version="13.0.4" />
       ```

   11. Under the console project's project dependencies, right-click `EditProjectLibrary` and select **Remove**.
   12. Verify that `EditProjectLibrary` is removed from the console project's dependencies.
   13. Return to `EditProjectConsole.csproj` and verify that the following entry has been removed:

       ```xml
       <ProjectReference Include="..\EditProjectLibrary\EditProjectLibrary.csproj" />
       ```
