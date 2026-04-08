package com.codepil.platform.mongodb;

import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.LastModifiedDate;

import java.time.Instant;
import java.util.UUID;

/**
 * Abstract base class for all MongoDB documents in the platform.
 *
 * <p>Provides three common fields that every MongoDB collection in the platform
 * should have:
 * <ul>
 *   <li>{@code id} — the MongoDB {@code _id} field, auto-generated as a UUID string.
 *       Using a UUID string rather than MongoDB's default {@code ObjectId} makes the ID
 *       safe to expose in REST APIs and Slack notifications without information leakage.</li>
 *   <li>{@code createdAt} — populated automatically by Spring Data MongoDB auditing
 *       ({@link org.springframework.data.mongodb.core.mapping.event.MongoAuditingEventListener})
 *       when the document is first saved.</li>
 *   <li>{@code updatedAt} — updated automatically by Spring Data MongoDB auditing
 *       on every subsequent save.</li>
 * </ul>
 * </p>
 *
 * <h3>Usage</h3>
 * <pre>
 * {@literal @}Document(collection = "orders")
 * public class Order extends BaseDocument {
 *     private String orderId;
 *     private String status;
 *     // getters / setters — no Lombok
 * }
 * </pre>
 *
 * <p>Auditing is enabled by {@link MongoConfig} via {@code @EnableMongoAuditing}.
 * Without this annotation, {@code @CreatedDate} and {@code @LastModifiedDate}
 * do not populate automatically.</p>
 */
public abstract class BaseDocument {

    /**
     * MongoDB document ID — stored as {@code _id} in the collection.
     *
     * <p>Auto-initialised to a UUID string on object creation. Because the ID is set
     * in the constructor (before MongoDB sees the document), Spring Data MongoDB treats
     * the document as "new" only if the {@code _id} is absent from the collection —
     * subsequent saves to the same ID perform an update (upsert).</p>
     */
    @Id
    private String id = UUID.randomUUID().toString();

    /**
     * Timestamp of document creation.
     *
     * <p>Set automatically by Spring Data MongoDB auditing on the first save.
     * Never updated on subsequent saves — use {@code updatedAt} for that.</p>
     */
    @CreatedDate
    private Instant createdAt;

    /**
     * Timestamp of the most recent document update.
     *
     * <p>Updated automatically by Spring Data MongoDB auditing on every save operation,
     * including the initial creation. Always reflects the wall-clock time of the last
     * {@code save()} or {@code insert()} call.</p>
     */
    @LastModifiedDate
    private Instant updatedAt;

    // -------------------------------------------------------------------------
    // Getters and Setters
    // -------------------------------------------------------------------------

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
