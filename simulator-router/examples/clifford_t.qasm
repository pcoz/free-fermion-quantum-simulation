// A small Clifford + T circuit, in QASM-lite form (a subset of OpenQASM 2.0).
// It has only TWO non-Clifford (T) gates, so the router picks the STABILIZER
// method -- cheap because the stabilizer simulator pays only in the T-count.
//
// Try it:   python simulator_router.py examples/clifford_t.qasm
// Experiment: delete the two `t` lines (pure Clifford -> still stabilizer, even
// cheaper); or add many more `t` lines to watch the stabilizer cost climb.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[16];

h q[0];
h q[7];
h q[8];
h q[15];
cx q[0],q[1];
cx q[6],q[7];
cx q[7],q[8];
cx q[8],q[9];
cx q[14],q[15];
cz q[3],q[4];
t q[7];
t q[8];
cx q[2],q[3];
