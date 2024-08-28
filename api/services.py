# from .forms import KeywordSearchForm
from .filters import BgcKeywordFilter
from .models import Bgc
from .utils import mgyb_converter

def search_bgcs_by_keyword(keyword):
    # Initialize the filter with the keyword
    bgc_filter = BgcKeywordFilter({'keyword': keyword}, queryset=Bgc.objects.all())
    results = bgc_filter.qs

    # Convert the mgyb integers back to the "MGYB{:012}" format for display
    for bgc in results:
        mgyb_converted = mgyb_converter(bgc.mgyb, text_to_int=False)
        bgc.mgybs = [mgyb_converted]
        bgc.bgc_detector_names = [bgc.bgc_detector.bgc_detector_name]
        bgc.bgc_class_names = [bgc.bgc_class.bgc_class_name]
        # print('mgyb_converted',bgc.mgyc)
    return results

def search_bgcs_by_advanced(criteria):
    pass