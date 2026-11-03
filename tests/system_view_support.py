"""Bind shared presentation through its public factory, without source slicing."""
import json
import support


def javascript(*, bind=True):
    names = ('t', 'esc', 'fmtNum', 'fmtDate', 'measurementLabel', 'levelChip', 'geneticComparisonHTML', 'genSummaryHtml', 'geneticCatalogueFold', 'panelLabsHtml', 'fib4Html', 'badge', 'sparkline', 'bodyMassMetric', 'genTableHtml', 'systemPolygenicHtml', 'thematicPanelLinks', 'correctionRoutesHtml', 'visibleTestProposals', 'testItem', 'basketRowHtml', 'systemLinkHtml', 'noteHtml', 'visitReportGenes')
    bindings = ','.join(name + ':(...args)=>' + name + '(...args)' for name in names)
    path = support.SRC / 'scholion/web/system-views.js'
    return ('const systemViews=require(' + json.dumps(str(path)) + ').create({' + bindings
            + ',flags:typeof FLAG!=="undefined"?FLAG:{},selected:id=>typeof visitSelection!=="undefined"&&visitSelection.has(id)});\n'
            + ('const {' + 'insightFactHTML,comparisonHTML,insightChartHTML,insightWindowsHTML,insightContextHTML,insightBasisHTML,attentionItemHTML,attentionHTML,visitInsightHTML,systemMedicationsHtml,systemCardHtml,actsOnHtml,medStatusText,controlsHtml,treatmentHtml,medItem,visitReportChart,visitReportSystem' + '}=systemViews;\n' if bind else ''))
