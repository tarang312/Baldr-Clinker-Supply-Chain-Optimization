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
    
    solvers_to_try = ['highs', 'glpk', 'cbc']
    results = None
    solved = False
    solver_used = None
    
    # 1. Try custom solver from solver.py (if available)
    try:
        from solver import solver as custom_solver
        try:
            results = custom_solver.solve(model, tee=verbose, load_solutions=True)
            if (results.solver.status == SolverStatus.ok) and \
               (results.solver.termination_condition in [TerminationCondition.optimal, 
                                                          TerminationCondition.feasible]):
                solved = True
                solver_used = "Custom Solver (solver.py)"
        except Exception as e:
            print(f"Custom solver failed: {e}")
    except ImportError:
        pass  # No custom solver available
    
    # 2. Try standard solvers in order
    if not solved:
        for solver_name in solvers_to_try:
            try:
                # Check if solver is available
                if not SolverFactory(solver_name).available():
                    continue
                
                # Attempt solve with solution loading
                opt = SolverFactory(solver_name)
                results = opt.solve(model, tee=verbose, load_solutions=True)
                
                # Check status
                if (results.solver.status == SolverStatus.ok) and \
                   (results.solver.termination_condition in [TerminationCondition.optimal,
                                                              TerminationCondition.feasible]):
                    solved = True
                    solver_used = solver_name.upper()
                    break
                    
            except Exception as e:
                print(f"Solver {solver_name} failed: {e}")
                continue
    
    # 3. Check final status
    if not solved:
        status_msg = "❌ All solvers failed (HiGHS, GLPK, CBC). Check model feasibility."
        return model, results, status_msg
    
    # Success!
    status_msg = f"✅ Solved successfully using {solver_used}"
    
    return model, results, status_msg


def get_solver_info(results) -> dict:
    """
    Extract solver information from results object.
    
    Args:
        results: Pyomo solver results
        
    Returns:
        Dictionary with solver details
    """
    info = {
        "status": str(results.solver.status),
        "termination_condition": str(results.solver.termination_condition),
        "solve_time": getattr(results.solver, 'time', 'N/A'),
        "iterations": getattr(results.solver, 'iteration_count', 'N/A')
    }
    
    return info
