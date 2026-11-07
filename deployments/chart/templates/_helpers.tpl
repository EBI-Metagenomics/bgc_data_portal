{{/*
Target namespace. Cloud manifests pin metadata.namespace explicitly, so we
render it from values rather than relying on the Helm release namespace. This
keeps `helm template` output identical to the hand-written manifests.
*/}}
{{- define "bgc.namespace" -}}
{{- .Values.namespace.name -}}
{{- end -}}
