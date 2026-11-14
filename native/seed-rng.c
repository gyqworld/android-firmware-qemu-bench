#include <stdint.h>
extern int open(const char*,int,...);extern int ioctl(int,unsigned long,...);extern int close(int);extern int dprintf(int,const char*,...);extern long read(int,void*,unsigned long);
int main(int argc,char**argv,char**env){
 struct{int entropy_count;int buf_size;unsigned char bytes[64];}s={.entropy_count=512,.buf_size=64};
 int seed=open("/bench/entropy",0);if(seed<0||read(seed,s.bytes,64)!=64)return 2;close(seed);
 int fd=open("/dev/random",2);int r=ioctl(fd,0x40085203UL,&s);close(fd);dprintf(1,"HOST_RANDOM_SEED_INJECTED result=%d bytes=64\n",r);return r?1:0;
}
extern void __libc_init(void*,void*,int(*)(int,char**,char**),const void*);
void bench_start(void*args){void*ctors[4]={0};__libc_init(args,0,main,ctors);}
__asm__(".global _start\n_start:\nmov x0, sp\nb bench_start\n");
