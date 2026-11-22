{{/*
Chart name.
*/}}
{{- define "firecrawl.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified release name.
*/}}
{{- define "firecrawl.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart label value.
*/}}
{{- define "firecrawl.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common metadata labels.
*/}}
{{- define "firecrawl.labels" -}}
helm.sh/chart: {{ include "firecrawl.chart" . }}
{{ include "firecrawl.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: firecrawl
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Labels shared by selectors and pods. Keep this set stable: selectors are
immutable after install.
*/}}
{{- define "firecrawl.selectorLabels" -}}
app.kubernetes.io/name: {{ include "firecrawl.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Pod labels before the component label is added.
*/}}
{{- define "firecrawl.podLabels" -}}
{{ include "firecrawl.selectorLabels" . }}
app.kubernetes.io/part-of: firecrawl
{{- end -}}

{{/*
Component name resolver. Usage:
  include "firecrawl.componentName" (dict "ctx" . "component" "api")
*/}}
{{- define "firecrawl.componentName" -}}
{{- $ctx := .ctx -}}
{{- $component := .component -}}
{{- $suffix := $component -}}
{{- if eq $component "nuqPostgres" -}}
{{- $suffix = "nuq-postgres" -}}
{{- end -}}
{{- $names := $ctx.Values.names | default dict -}}
{{- $override := index $names $component | default "" -}}
{{- if $override -}}
{{- $override | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" (include "firecrawl.fullname" $ctx) $suffix | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Secret name resolver.
*/}}
{{- define "firecrawl.secretName" -}}
{{- if .Values.existingSecret -}}
{{- .Values.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "firecrawl.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Container image reference. A digest wins over a tag.
*/}}
{{- define "firecrawl.image" -}}
{{- if .digest -}}
{{- printf "%s@%s" .repository .digest -}}
{{- else -}}
{{- printf "%s:%s" .repository (.tag | default "latest") -}}
{{- end -}}
{{- end -}}
