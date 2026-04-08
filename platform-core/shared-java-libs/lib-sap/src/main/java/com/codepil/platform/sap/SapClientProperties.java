package com.codepil.platform.sap;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Typed configuration properties for SAP connectivity.
 *
 * <p>Binds all SAP-related properties from {@code application.yml} under the {@code sap} prefix.
 * This centralises SAP credentials and endpoint configuration in a single, type-safe POJO
 * rather than scattering {@code @Value} annotations across multiple classes.</p>
 *
 * <h3>application.yml example</h3>
 * <pre>
 * sap:
 *   gateway-url: https://sap-gateway.example.com/sap/opu/odata/sap
 *   oauth-token-url: https://sap-gateway.example.com/sap/bc/sec/oauth2/token
 *   client-id: ${SAP_CLIENT_ID}
 *   client-secret: ${SAP_CLIENT_SECRET}
 *   jco-host: sap-host.example.com
 *   jco-client: "100"
 *   jco-user: ${SAP_JCO_USER}
 *   jco-password: ${SAP_JCO_PASSWORD}
 * </pre>
 *
 * <h3>Environment variables (never hard-code credentials)</h3>
 * <ul>
 *   <li>{@code SAP_CLIENT_ID} — OAuth2 client ID for SAP Gateway</li>
 *   <li>{@code SAP_CLIENT_SECRET} — OAuth2 client secret for SAP Gateway</li>
 *   <li>{@code SAP_JCO_USER} — JCo RFC user</li>
 *   <li>{@code SAP_JCO_PASSWORD} — JCo RFC password</li>
 * </ul>
 */
@Component
@ConfigurationProperties(prefix = "sap")
public class SapClientProperties {

    /** Base URL of the SAP OData Gateway (e.g. {@code https://sap-gateway.example.com/sap/opu/odata/sap}). */
    private String gatewayUrl;

    /** OAuth2 token endpoint URL for SAP Gateway client credentials flow. */
    private String oauthTokenUrl;

    /** OAuth2 client ID registered in SAP for the platform service. */
    private String clientId;

    /** OAuth2 client secret (injected from environment variable {@code SAP_CLIENT_SECRET}). */
    private String clientSecret;

    /** SAP Application Server host for JCo RFC connections. */
    private String jcoHost;

    /** SAP client number (Mandant) — typically {@code "100"} for production. */
    private String jcoClient;

    /** SAP system number for JCo RFC connections (e.g. {@code "00"}). */
    private String jcoSystemNumber = "00";

    /** SAP user for JCo RFC authentication. */
    private String jcoUser;

    /** SAP password for JCo RFC authentication (injected from environment variable). */
    private String jcoPassword;

    /** SAP language for BAPI/RFC calls (default: {@code EN}). */
    private String jcoLanguage = "EN";

    /** Maximum number of JCo connections in the connection pool (default: 5). */
    private int jcoPoolCapacity = 5;

    /** Maximum number of concurrent JCo conversations (default: 10). */
    private int jcoMaxConnections = 10;

    // -------------------------------------------------------------------------
    // Getters and Setters — required for @ConfigurationProperties binding
    // -------------------------------------------------------------------------

    public String getGatewayUrl() {
        return gatewayUrl;
    }

    public void setGatewayUrl(String gatewayUrl) {
        this.gatewayUrl = gatewayUrl;
    }

    public String getOauthTokenUrl() {
        return oauthTokenUrl;
    }

    public void setOauthTokenUrl(String oauthTokenUrl) {
        this.oauthTokenUrl = oauthTokenUrl;
    }

    public String getClientId() {
        return clientId;
    }

    public void setClientId(String clientId) {
        this.clientId = clientId;
    }

    public String getClientSecret() {
        return clientSecret;
    }

    public void setClientSecret(String clientSecret) {
        this.clientSecret = clientSecret;
    }

    public String getJcoHost() {
        return jcoHost;
    }

    public void setJcoHost(String jcoHost) {
        this.jcoHost = jcoHost;
    }

    public String getJcoClient() {
        return jcoClient;
    }

    public void setJcoClient(String jcoClient) {
        this.jcoClient = jcoClient;
    }

    public String getJcoSystemNumber() {
        return jcoSystemNumber;
    }

    public void setJcoSystemNumber(String jcoSystemNumber) {
        this.jcoSystemNumber = jcoSystemNumber;
    }

    public String getJcoUser() {
        return jcoUser;
    }

    public void setJcoUser(String jcoUser) {
        this.jcoUser = jcoUser;
    }

    public String getJcoPassword() {
        return jcoPassword;
    }

    public void setJcoPassword(String jcoPassword) {
        this.jcoPassword = jcoPassword;
    }

    public String getJcoLanguage() {
        return jcoLanguage;
    }

    public void setJcoLanguage(String jcoLanguage) {
        this.jcoLanguage = jcoLanguage;
    }

    public int getJcoPoolCapacity() {
        return jcoPoolCapacity;
    }

    public void setJcoPoolCapacity(int jcoPoolCapacity) {
        this.jcoPoolCapacity = jcoPoolCapacity;
    }

    public int getJcoMaxConnections() {
        return jcoMaxConnections;
    }

    public void setJcoMaxConnections(int jcoMaxConnections) {
        this.jcoMaxConnections = jcoMaxConnections;
    }
}
