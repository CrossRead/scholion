"""Bind the shipped measurement component directly; never slice its source."""
import json
import support


def javascript():
    path = support.SRC / 'scholion/web/measurements.js'
    names = ('t', 'esc', 'fmtNum', 'fmtDate', 'targetSpec', 'flagOf', 'trendNote',
             'badge', 'refText', 'targetText', 'ownerNoteHtml', 'systemLinkHtml',
             'decisionNote', 'noteHtml', 'targetAsk', 'srcTag', 'comparisonHTML')
    bindings = ','.join(name + ':(...args)=>' + name + '(...args)' for name in names)
    return ('const measurements=require(' + json.dumps(str(path)) + ').create({' + bindings
            + ',flags:typeof FLAG!=="undefined"?FLAG:{},line:(...args)=>gline(...args),colours:()=>CT});\n'
            + 'const measurementLabel=measurements.label,measurementGroups=measurements.groups,'
            + 'bodyMassMetric=measurements.isBodyMass,measurementDatasets=measurements.datasets,'
            + 'sparkline=measurements.sparkline;\n'
            + "const markerCard=m=>measurements.render(m,'lab');\n")
