#include <stddef.h>
extern void *dlopen(const char*,int);extern void *dlsym(void*,const char*);extern char *dlerror(void);
extern int dprintf(int,const char*,...);
int main(int argc,char **argv,char **env){
 void *h=dlopen("/vendor/lib64/egl/libEGL_swiftshader.so",2);
 dprintf(1,"SWIFTSHADER_DLOPEN=%p error=%s\n",h,h?"none":dlerror());if(!h)return 1;
 void*(*display)(void*)=dlsym(h,"eglGetDisplay");int(*init)(void*,int*,int*)=dlsym(h,"eglInitialize");
 const char*(*query)(void*,int)=dlsym(h,"eglQueryString");void*d=display(0);int a=0,b=0;int r=init(d,&a,&b);
 dprintf(1,"EGL_INIT=%d VERSION=%d.%d VENDOR=%s\n",r,a,b,r?query(d,0x3053):"failed");return r?0:2;
}
extern void __libc_init(void*,void*,int(*)(int,char**,char**),const void*);
void bench_start(void *args){void*ctors[4]={0};__libc_init(args,0,main,ctors);}
__asm__(".global _start\n_start:\nmov x0, sp\nb bench_start\n");
