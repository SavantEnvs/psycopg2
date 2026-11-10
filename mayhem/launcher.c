/* ELF shim: Mayhem needs an ELF cmd, so exec `python3 <PY_SCRIPT> <args...>`. */
#include <stdlib.h>
#include <unistd.h>

#ifndef PY_SCRIPT
#error "define PY_SCRIPT"
#endif

int main(int argc, char **argv) {
    char **nv = (char **)malloc((size_t)(argc + 2) * sizeof(char *));
    if (!nv) return 1;
    nv[0] = (char *)"python3";
    nv[1] = (char *)PY_SCRIPT;
    for (int i = 1; i < argc; i++) nv[i + 1] = argv[i];
    nv[argc + 1] = NULL;
    execvp("python3", nv);
    return 127;
}
