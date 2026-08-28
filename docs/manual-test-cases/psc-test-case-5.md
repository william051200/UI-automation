# Verify the F# xUnit template in Test Explorer

## Prerequisites

- Ensure that **F# desktop language support** is installed for Visual Studio through Visual Studio Installer.
- Ensure that the machine can restore NuGet packages required by the xUnit test project.

## Test steps

1. Create an **F# Class Library** project.

   1. Open Visual Studio and click **Create a new project**.
   2. Set the language filter to **F#**.
   3. Select **Class Library** and click **Next**.
   4. Set **Project name** to `FSharpLibrary`.
   5. Set **Solution name** to `FSharpXunit`.
   6. Keep the other project settings unchanged and click **Next**.
   7. Select **.NET Standard 2.0** and click **Create**.

2. Replace the contents of `Library.fs` with:

```fsharp
namespace FSharpLibrary

module Say =
    let func1 x = x + 3
    let result1 = func1 4
    printfn "The result of x adding 3 is %d" result1
```

3. Add an **F# xUnit Test Project** to the solution.

   1. Select **File > Add > New Project...**.
   2. Set the language filter to **F#**.
   3. Select **xUnit Test Project** and click **Next**.
   4. Set **Project name** to `FSharpTests`.
   5. Keep the solution location and other project settings unchanged.
   6. Select **.NET 10.0** and click **Create**.

4. Add the class library as a dependency of the test project.

   1. Select **View > Solution Explorer**.
   2. Right-click the `FSharpTests` project and select **Add > Project Reference...**.
   3. In **Reference Manager**, select **Projects > Solution**.
   4. Select `FSharpLibrary` and click **OK**.

5. Replace the contents of `Tests.fs` with:

```fsharp
module Tests

open Xunit

[<Fact>]
let ``My test1`` () =
    Assert.Equal(7, FSharpLibrary.Say.result1)

[<Fact>]
let ``My test2`` () =
    Assert.Equal(71, FSharpLibrary.Say.result1)
```

6. Select **Build > Rebuild Solution**.

7. Verify in the **Output** window that both projects rebuild successfully with no errors.

8. Select **Test > Test Explorer**.

9. Wait for Test Explorer to discover `My test1` and `My test2`.

10. Click **Run All Tests** in Test Explorer.

11. Verify that the first test run completes with the following result:

```text
2 Tests
1 Passed
1 Failed
0 Skipped
```

12. Verify that `My test1` shows the cyan/green passed indicator and `My test2` shows the red failed indicator in Test Explorer.

13. In Test Explorer, right-click the failed `My test2` test and select **Debug**.

14. Verify that the debugger stops on the failing assertion and Visual Studio displays **Exception User-Unhandled**.

15. Verify that the exception details contain:

```text
Xunit.Sdk.EqualException: 'Assert.Equal() Failure: Values differ
Expected: 71
Actual: 7'
```

16. Select **Debug > Stop Debugging**.

17. In `Tests.fs`, change the expected value in `My test2` from `71` to `7`:

```fsharp
[<Fact>]
let ``My test2`` () =
    Assert.Equal(7, FSharpLibrary.Say.result1)
```

18. Save `Tests.fs`.

19. Click **Run All Tests** in Test Explorer again.

20. Verify that the final test run completes with the following result:

```text
2 Tests
2 Passed
0 Failed
0 Skipped
```

21. Verify that both `My test1` and `My test2` have a passed status and that the test output reports a successful run.
