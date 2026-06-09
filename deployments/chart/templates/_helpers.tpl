{{/*
Target namespace. Cloud manifests pin metadata.namespace explicitly, so we
render it from values rather than relying on the Helm release namespace. This
keeps `helm template` output identical to the hand-written manifests.
*/}}
{{- define "bgc.namespace" -}}
{{- .Values.namespace.name -}}
{{- end -}}

{{/*
Shared envFrom block: every workload pulls the app Secret, and (when enabled)
the app/proxy ConfigMap. Render at the container's envFrom indentation.
*/}}
{{- define "bgc.envFrom" -}}
- secretRef:
    name: {{ .Values.secretName }}
{{- if .Values.config.enabled }}
- configMapRef:
    name: {{ .Values.config.name }}
{{- end }}
{{- end -}}
