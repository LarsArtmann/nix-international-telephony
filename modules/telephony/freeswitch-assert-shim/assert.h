/* gcc-16 + glibc-2.44 compatibility shim, injected as the first -I of the
 * FreeSWITCH build.
 *
 * glibc 2.44's <assert.h> is deliberately re-includable: every inclusion
 * unguards (_ASSERT_H), re-parses the C23 `__assert_single_arg` declaration,
 * and gcc 16 mis-merges the identical redeclaration into a hard
 * "conflicting types" error. FreeSWITCH's TUs routinely reach <assert.h>
 * through two header chains (switch.h and a third-party lib), so the
 * declaration conflict alone kills the build — and the C23 assert macro's
 * sizeof (__assert_single_arg (expr)) expansion additionally hard-errors
 * on pointer asserts. -std=gnu17 does NOT help: config.h's _GNU_SOURCE
 * re-enables the ISOC23 machinery regardless of the language revision.
 *
 * The self-guard pins the parse to a single inclusion and reinstates the
 * classic assert macro (same __assert_fail linkage, same semantics).
 * Remove once the toolchain class is fixed upstream.
 */
#ifndef PBX_FREESWITCH_ASSERT_SHIM_H
#define PBX_FREESWITCH_ASSERT_SHIM_H

#include_next <assert.h>

#undef assert

#ifdef NDEBUG
#define assert(expr) ((void) 0)
#else
#define assert(expr) \
  ((expr) ? (void) 0 : __assert_fail (#expr, __FILE__, __LINE__, __func__))
#endif

#endif
