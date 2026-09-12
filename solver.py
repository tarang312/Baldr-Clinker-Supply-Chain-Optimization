from pyomo.environ import SolverFactory
import sys

class SolverWrapper:
    def solve(self, model, tee=False, load_solutions=False):
        # 1. Try Pyomo APPSI Highs directly (via highspy)
        try:
            from pyomo.contrib.appsi.solvers import Highs
            highs_appsi = Highs()
            if highs_appsi.available():
                print("SolverWrapper: Optimizing using APPSI Highs...")
                return highs_appsi.solve(model)
        except Exception as e:
            print(f"SolverWrapper: APPSI Highs direct solve failed: {e}")

        # 2. Fallback to standard Pyomo SolverFactory solvers
        solvers_to_try = ['appsi_highs', 'highs', 'glpk', 'cbc', 'ipopt']
        
        for s_name in solvers_to_try:
            try:
                temp_opt = SolverFactory(s_name)
                available = False
                try:
                    available = temp_opt.available()
                except Exception:
                    available = False
                
                if available:
                    print(f"SolverWrapper: Found solver '{s_name}'")
                    try:
                        return temp_opt.solve(model, tee=tee)
                    except TypeError:
                        return temp_opt.solve(model)
            except Exception as e:
                print(f"SolverWrapper: Error with '{s_name}': {e}")
                continue
        
        msg = "No suitable solver found. Checked: " + ", ".join(solvers_to_try) + ". Please ensure highspy is installed."
        print(msg)
        raise RuntimeError(msg)

solver = SolverWrapper()
