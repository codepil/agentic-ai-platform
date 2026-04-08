package com.codepil.platform.sap;

/**
 * Exception thrown when a SAP BAPI/RFC call fails.
 *
 * <p>Wraps JCo exceptions and BAPI return-table errors into a single platform
 * exception type. Callers can catch this exception specifically to handle SAP
 * connectivity or business-logic failures without coupling to JCo's exception
 * hierarchy.</p>
 */
public class SapBapiException extends RuntimeException {

    public SapBapiException(String message) {
        super(message);
    }

    public SapBapiException(String message, Throwable cause) {
        super(message, cause);
    }
}
