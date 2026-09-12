from pyomo.environ import SolverFactory
import sys

class SolverWrapper:
    def solve(self, model, tee=False, load_solutions=False):
        # Solvers to try. 'appsi_highs' comes from the pip-installable 'highspy' package.
        # 'highs', 'glpk', 'cbc' usually require external binaries in PATH.
        solvers_to_try = ['appsi_highs', 'highs', 'glpk', 'cbc', 'ipopt']
        
        opt = None
        used_solver = None
        
        print("SolverWrapper: Checking for available solvers...")
        
        for s_name in solvers_to_try:
            try:
                temp_opt = SolverFactory(s_name)
                # Check availability (handle both True/False and Exceptions)
                available = False
                try:
                    available = temp_opt.available()
                except Exception as e:
                    print(f"Solver '{s_name}' check failed with error: {e}")
                    available = False
                
                if available:
                    opt = temp_opt
                    used_solver = s_name
                    print(f"SolverWrapper: Found solver '{s_name}'")
                    break
                else:
                    print(f"SolverWrapper: Solver '{s_name}' not available")
            except Exception as e:
                print(f"SolverWrapper: Error initializing '{s_name}': {e}")
                continue
        
        if opt is None:
            msg = (
                "No suitable solver found. Checked: " + ", ".join(solvers_to_try) + ".\n"
                "Please ensure a solver is installed. Recommended: 'pip install highspy'"
            )
            print(msg)
            # Raise a cleaner error that might be caught by the UI or at least readable
            raise RuntimeError(msg)
            
        print(f"SolverWrapper: Optimizing using {used_solver}...")
        return opt.solve(model, tee=tee, load_solutions=load_solutions)

solver = SolverWrapper()
