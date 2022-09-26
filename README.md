# Scripts

Hej!

This is a repo of various helper scripts that I've made to aid my game development etc.

The scripts are probably somewhat messy and undocumented but they might be useful if you're looking to solve a similar problem.

## Index of scripts

### DiffUE.py

Solution/work-around to the problem of not being able to visually diff .uasset files in from Unreal Engine when using my experimental "[separating content from code](https://ljung.dev/tutorial/unreal-engine-and-git-separating-content-from-code/)" git workflow.

If works by setting up and constructing the prerequisites for running the `-diff` command of the Unreal Engine binary, which will open the "Blueprint Diff" dialog for the provided files.

The accompanying DiffUE.bat is a simple wrapper that passes all arguments to the script, assuming the script is in the same directory. The .bat file can be put in your (Windows) Path env to enable running `DiffUE.bat <file>` from anywhere.

Tested with Windows 10, Python 3.10.2, Unreal Engine 5.0.3.
