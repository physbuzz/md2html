Step 1: Parse files to be watched

Nodes in the DAG can be...
- No build needed for this file, but notify downstream files to be rebuilt. (for example, `_header.md` would never be built into `_header.html`, but we do need to notify every app that includes `@include(_header.md)`.)
- Copy and paste to output directory (so, `relative_path/file.png` should be watched so that we can copy and paste it to `output_dir/relative_path/file.png` if it's updated. Also, even files like `file.cpp` get copied.)
- Build markdown (so, `relative_path/file.md` should be watched so that whenever it's updated we rebuild `output_dir/relative_path/file.html`, together with watching for recursive includes.)
- Build program (so, if the execute flag is set and if `file.md` has `@src(file.cpp)` included, we attempt to compile it, run it, save its std out to `_file.out`, and then rebuild file.md.)

If argument is a directory:
    If recursive flag is not set, throw an error.
    Else fetch all files recursively: 
        All files and directories beginning with an underscore get ignored.
        For all files with a .md extension:
            1. Create a build step (dependency graph edge) given the input file to build 
               output_dir/(relative path).html using the markdown builder.
            2. Parse through the file to get all @src includes and @include includes. (Files included explicitly may begin with an underscore, these files are not ignored)
               1. For all @src includes, if the execute flag is set, create a build step 
                  from file.program to _file.out. (DAG graph, this build step will involve
                  running something like `g++ file.cpp -o _a.out && ./_a.out > _file.out`, it is meant for
                  very basic build commands.)
               2. For all @include includes, we need to watch for the update when these files are changed
                  but we do not need to build the includes. We should however recursively search for includes.
        All files with a .html extension get the liquid (jekyll-like) treatment w/ output file
            output_dir/(relative path).html, conflicts w/ md are warned about and one is chosen.
        Other files are copied to output_dir/(relative_path)