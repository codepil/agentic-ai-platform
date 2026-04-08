package com.codepil.platform.mongodb;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.MongoDatabaseFactory;
import org.springframework.data.mongodb.MongoTransactionManager;
import org.springframework.data.mongodb.config.EnableMongoAuditing;
import org.springframework.data.mongodb.core.convert.MongoCustomConversions;

import java.util.ArrayList;

/**
 * MongoDB configuration providing auditing support for all platform services.
 *
 * <h3>What this enables</h3>
 * <ul>
 *   <li>{@code @EnableMongoAuditing} — activates Spring Data MongoDB's auditing support.
 *       Without this, {@code @CreatedDate} and {@code @LastModifiedDate} fields in
 *       {@link BaseDocument} (and all subclasses) are never populated.</li>
 *   <li>{@link MongoTransactionManager} — enables multi-document transactions where needed.
 *       Note: MongoDB transactions require a replica set or sharded cluster (Atlas M10+).</li>
 * </ul>
 *
 * <h3>How to include in a generated product service</h3>
 * <p>Add {@code lib-mongodb} to the service's {@code pom.xml}. Spring Boot's auto-configuration
 * will pick up this {@code @Configuration} class from the classpath automatically via
 * component scanning, provided the base package is included in {@code @SpringBootApplication}.</p>
 *
 * <p>To ensure this config class is picked up from a library jar, add the service's main
 * package scan to include {@code com.codepil.platform.mongodb}:
 * <pre>
 * {@literal @}SpringBootApplication(scanBasePackages = {
 *     "com.codepil.catalog",          // product service package
 *     "com.codepil.platform.mongodb"  // lib-mongodb package
 * })
 * </pre>
 * Or register it via {@code spring.factories} / {@code @AutoConfiguration} if preferred.
 * </p>
 */
@Configuration
@EnableMongoAuditing
public class MongoConfig {

    /**
     * Register custom MongoDB type converters.
     *
     * <p>Currently empty — Java 21 {@code Instant} is handled natively by Spring Data MongoDB 4.x.
     * Add custom converters here if additional type mappings are needed (e.g. enums, value objects).</p>
     *
     * @return empty custom conversions (placeholder for future converters)
     */
    @Bean
    public MongoCustomConversions mongoCustomConversions() {
        return new MongoCustomConversions(new ArrayList<>());
    }

    /**
     * Enable multi-document transactions via MongoDB's transaction API.
     *
     * <p>Required for any service method that modifies multiple MongoDB collections
     * atomically. The {@code MongoDatabaseFactory} is auto-configured by Spring Boot
     * based on the {@code spring.data.mongodb.uri} property.</p>
     *
     * <p>Transactions are only supported on replica sets (MongoDB Atlas M10+ or a local
     * replica set). In development with a standalone MongoDB, calls to methods annotated
     * {@code @Transactional} will succeed but without transaction semantics.</p>
     *
     * @param dbFactory the MongoDB database factory
     * @return the transaction manager
     */
    @Bean
    public MongoTransactionManager transactionManager(MongoDatabaseFactory dbFactory) {
        return new MongoTransactionManager(dbFactory);
    }
}
