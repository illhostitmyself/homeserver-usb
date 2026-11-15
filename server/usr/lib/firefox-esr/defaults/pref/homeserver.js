// Every app on the server is plain HTTP inside the home network, so Firefox's "This connection is
// not secure" popup on each login form only confuses.
pref("security.insecure_field_warning.contextual.enabled", false);
