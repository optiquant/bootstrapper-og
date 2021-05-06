import _model.bootstrapper_charts as bootstrapper_charts
import _model.financing as financing

financing.run_financing()
bootstrapper_charts._initialize()
bootstrapper_charts.build_financing_charts()