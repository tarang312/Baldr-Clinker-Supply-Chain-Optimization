"""
Solver Engine Module
====================
Robust multi-stage solver execution with fallback logic.

Attempts solvers in order:
1. Custom solver from solver.py (if available)
2. HiGHS (recommended for LP/MILP)
3. GLPK (fallback)
4. CBC (last resort)
"""

from pyomo.environ import *
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition
try:
    import streamlit as st
except ImportError:
    st = None
from typing import Tuple, Optional


def solve_model(model: ConcreteModel, verbose: bool = False) -> Tuple[ConcreteModel, Any, str]:
    """
    Solve Pyomo model with robust multi-stage solver logic.
    
    Args:
        model: Pyomo ConcreteModel to solve
        verbose: If True, show solver output (tee=True)
        
    Returns:
        Tuple of (model, results, status_message)
        - model: Solved model with variable values loaded
        - results: Pyomo solver results object
        - status_message: Human-readable status string
    """
    
def is_solver_result_ok(results) -> bool:
    """Helper to check if results indicate optimal or feasible solution."""
    if results is None:
        return False
    if hasattr(results, 'termination_condition'):
        tc = results.termination_condition
        if tc in [TerminationCondition.optimal, TerminationCondition.feasible]:
            return True
    if hasattr(results, 'solver'):
        status = getattr(results.solver, 'status', None)
        tc = getattr(results.solver, 'termination_condition', None)
        if status == SolverStatus.ok and tc in [TerminationCondition.optimal, TerminationCondition.feasible]:
            return True
    return False


def solve_model(model: ConcreteModel, verbose: bool = False) -> Tuple[ConcreteModel, Any, str]:
    """
    Solve Pyomo model with robust multi-stage solver logic.
    """
    solvers_to_try = ['appsi_highs', 'highs', 'glpk', 'cbc']
    results = None
    solved = False
    solver_used = None
    
    # 1. Try custom solver from solver.py (if available)
    try:
        from solver import solver as custom_solver
        try:
            results = custom_solver.solve(model, tee=verbose, load_solutions=True)
            if is_solver_result_ok(results):
                solved = True
                solver_used = "Custom Solver (solver.py)"
        except Exception as e:
            print(f"Custom solver failed: {e}")
    except ImportError:
        pass
    
    # 2. Try direct APPSI Highs if not solved yet
    if not solved:
        try:
            from pyomo.contrib.appsi.solvers import Highs
            highs_appsi = Highs()
            if highs_appsi.available():
                results = highs_appsi.solve(model)
                if is_solver_result_ok(results):
                    solved = True
                    solver_used = "HiGHS (APPSI)"
        except Exception as e:
            print(f"APPSI Highs direct attempt failed: {e}")

    # 3. Try standard solvers in order
    if not solved:
        for solver_name in solvers_to_try:
            try:
                if not SolverFactory(solver_name).available():
                    continue
                opt = SolverFactory(solver_name)
                try:
                    results = opt.solve(model, tee=verbose)
                except TypeError:
                    results = opt.solve(model)
                
                if is_solver_result_ok(results):
                    solved = True
                    solver_used = solver_name.upper()
                    break
            except Exception as e:
                print(f"Solver {solver_name} failed: {e}")
                continue
    
    # 4. Check final status
    if not solved:
        status_msg = "❌ All solvers failed (HiGHS, GLPK, CBC). Check model feasibility."
        return model, results, status_msg
    
    status_msg = f"✅ Solved successfully using {solver_used}"
    return model, results, status_msg


def get_solver_info(results) -> dict:
    """Extract solver information from results object."""
    if results is None:
        return {"status": "Unknown"}
    if hasattr(results, 'termination_condition'):
        return {
            "status": "ok",
            "termination_condition": str(results.termination_condition),
            "solve_time": getattr(results, 'solve_time', 'N/A')
        }
    if hasattr(results, 'solver'):
        return {
            "status": str(getattr(results.solver, 'status', 'N/A')),
            "termination_condition": str(getattr(results.solver, 'termination_condition', 'N/A')),
            "solve_time": getattr(results.solver, 'time', 'N/A'),
            "iterations": getattr(results.solver, 'iteration_count', 'N/A')
        }
    return {"status": str(results)}
