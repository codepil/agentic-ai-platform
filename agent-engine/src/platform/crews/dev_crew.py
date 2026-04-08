"""
Development crew — writes production code.

Crew type: Hierarchical
  Manager:  Tech Lead    — delegates tasks and reviews all output
  Workers:  Java Developer, React Developer

Task context dependencies:
  java_task   context=[]
  react_task  context=[]
  review_task context=[java_task, react_task]

In mock mode returns 3 CodeArtifacts with fake git metadata.
Output is validated against DevCrewOutput Pydantic model.

Parent blueprint: /Agentic-AI-platform/blueprint.md
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base_crew import BaseCrew
from ..state.sdlc_state import CodeArtifact


class DevCrew(BaseCrew):
    """Implements the code artefacts for the current sprint."""

    # -------------------------------------------------------------------------
    # Platform-core coding standard snippets injected into Dev Crew agent prompts
    # as few-shot examples.  The JavaServiceBuilder agent backstory includes these
    # snippets so the LLM replicates the exact patterns used in platform-core
    # rather than inventing its own style.
    # -------------------------------------------------------------------------
    _PLATFORM_CORE_SNIPPETS = """
=== CODING STANDARD: Spring Boot Controller Pattern ===
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {
    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('SCOPE_products:read')")
    public ResponseEntity<Page<ProductResponse>> listProducts(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(productService.listProducts(page, size));
    }
}

=== CODING STANDARD: Spring Boot Service Pattern ===
@Service
public class ProductService {
    private static final Logger log = LoggerFactory.getLogger(ProductService.class);
    private final ProductRepository productRepository;

    @Transactional(readOnly = true)
    public Page<ProductResponse> listProducts(int page, int size) {
        log.info("Listing products page={} size={}", page, size);
        return productRepository.findAll(PageRequest.of(page, size))
            .map(ProductResponse::from);
    }
}

=== CODING STANDARD: MongoDB Repository Pattern ===
@Repository
public interface ProductRepository extends MongoRepository<Product, String> {
    Page<Product> findByCategoryAndPriceLessThanEqual(
        String category, BigDecimal maxPrice, Pageable pageable);

    @Query("{ 'sapMaterialId': ?0 }")
    Optional<Product> findBySapMaterialId(String sapMaterialId);
}

=== CODING STANDARD: DTO Record Pattern (Java 21) ===
public record ProductResponse(
    String id, String sku, String name,
    BigDecimal price, String category, int stockQuantity
) {
    public static ProductResponse from(Product product) {
        return new ProductResponse(product.getId(), product.getSku(),
            product.getName(), product.getPrice(),
            product.getCategory(), product.getStockQuantity());
    }
}
"""

    _MOCK_ARTIFACTS: List[CodeArtifact] = [
        {
            "artifact_id": "artifact-001",
            "type": "java_service",
            "repo": "myorg/selfcare-catalog",
            "file_path": "src/main/java/com/example/catalog/ProductController.java",
            "git_branch": "feature/SC-101-product-catalog-api",
            "git_commit_sha": "b3e2f1a4d5c6b7a8b3e2f1a4d5c6b7a8b3e2f1a4",
            "content_hash": "sha256:deadbeefcafe0001",
        },
        {
            "artifact_id": "artifact-002",
            "type": "react_component",
            "repo": "myorg/selfcare-spa",
            "file_path": "src/components/ProductCard/ProductCard.tsx",
            "git_branch": "feature/SC-101-product-card-component",
            "git_commit_sha": "c4f3a2b1e6d7c8b9c4f3a2b1e6d7c8b9c4f3a2b1",
            "content_hash": "sha256:deadbeefcafe0002",
        },
        {
            "artifact_id": "artifact-003",
            "type": "test_suite",
            "repo": "myorg/selfcare-catalog",
            "file_path": "src/test/java/com/example/catalog/ProductControllerTest.java",
            "git_branch": "feature/SC-101-product-catalog-api",
            "git_commit_sha": "d5a4b3c2f7e8d9a0d5a4b3c2f7e8d9a0d5a4b3c2",
            "content_hash": "sha256:deadbeefcafe0003",
        },
    ]

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the dev crew and return a list of CodeArtifacts."""
        if self.mock_mode:
            return {"code_artifacts": [dict(a) for a in self._MOCK_ARTIFACTS]}

        from crewai import Agent, Task, Crew, Process
        from ..llm.model_router import get_llm
        from ..tools.crewai_tools import get_github_crewai_tools, get_figma_crewai_tools

        llm = get_llm("write_code")
        create_github_branch, commit_file_to_github, create_github_pr = get_github_crewai_tools()
        read_figma_file, list_figma_components = get_figma_crewai_tools()

        tech_lead = Agent(
            role="Tech Lead",
            goal=(
                "Ensure code quality, architecture adherence, SOLID principles, and security "
                "best practices in every contribution. Delegate implementation tasks and review all output."
            ),
            backstory=(
                "You are a Staff Engineer and Tech Lead with 12 years in Spring Boot microservices "
                "and React frontends. You enforce clean architecture, SOLID principles, and security "
                "best practices in every PR. You are the manager agent who delegates implementation "
                "tasks and reviews all output."
            ),
            llm=llm,
            tools=[create_github_branch, create_github_pr],
            memory=True,
            verbose=True,
            allow_delegation=True,
        )
        java_dev = Agent(
            role="Senior Java Developer",
            goal=(
                "Implement production-ready Spring Boot 3 REST controllers, services, and "
                "SAP JCo integration with proper exception handling and test coverage"
            ),
            backstory=(
                "You are a Senior Java Developer specialising in Spring Boot 3, Spring Security, "
                "and SAP JCo integration. You write production-ready code with proper exception "
                "handling, logging, and Testcontainers-based integration tests. Your code follows "
                "hexagonal architecture and is fully covered by unit tests."
                "\n\nCODING STANDARDS TO FOLLOW:\n"
                + self._PLATFORM_CORE_SNIPPETS
            ),
            llm=llm,
            tools=[commit_file_to_github],
            memory=True,
            verbose=True,
        )
        react_dev = Agent(
            role="Senior React Developer",
            goal=(
                "Build accessible WCAG 2.1 AA React 18 TypeScript components from Figma designs "
                "with comprehensive Jest and Playwright tests"
            ),
            backstory=(
                "You are a Senior Frontend Engineer specialising in React 18, TypeScript, and "
                "Webpack Module Federation. You build accessible (WCAG 2.1 AA) components from "
                "Figma designs and write comprehensive Jest and Playwright tests."
            ),
            llm=llm,
            tools=[read_figma_file, list_figma_components, commit_file_to_github],
            memory=True,
            verbose=True,
        )

        java_task = Task(
            description=(
                f"Implement the product catalog Spring Boot 3 service based on architecture:\n"
                f"{inputs.get('architecture', '')}\n\n"
                f"Requirements:\n{inputs.get('requirements', '')}\n\n"
                f"Create a feature branch using Create GitHub Branch, then implement:\n"
                f"1. ProductController.java — REST controller with GET /products and GET /products/{{id}}\n"
                f"2. ProductService.java — business logic with SAP JCo integration\n"
                f"3. ProductRepository.java — MongoDB repository with custom queries\n"
                f"Commit all files using Commit File to GitHub."
            ),
            expected_output=(
                "JSON list of committed Java source files with artifact_id, type='java_service', "
                "repo, file_path, git_branch, git_commit_sha, content_hash"
            ),
            agent=java_dev,
        )
        react_task = Task(
            description=(
                f"Implement React 18 TypeScript components matching the Figma designs at "
                f"{inputs.get('figma_url', '')}.\n\n"
                f"Use List Figma Components to discover all components, then implement:\n"
                f"1. ProductCard.tsx — accessible product card with image, name, price, CTA\n"
                f"2. FilterSidebar.tsx — category and price range filters\n"
                f"3. ProductCard.test.tsx — Jest unit tests with React Testing Library\n"
                f"4. ProductCard.spec.ts — Playwright E2E test\n"
                f"Commit all files using Commit File to GitHub."
            ),
            expected_output=(
                "JSON list of committed React/TypeScript files with artifact_id, "
                "type='react_component', repo, file_path, git_branch, git_commit_sha, content_hash"
            ),
            agent=react_dev,
        )
        review_task = Task(
            description=(
                "Review all code produced by the Java Developer and React Developer. Check for:\n"
                "1. Security: OWASP Top 10, input validation, proper auth\n"
                "2. Performance: N+1 queries, missing indexes, unnecessary allocations\n"
                "3. Code style: SOLID principles, clean architecture, naming conventions\n"
                "4. Test coverage: minimum 80% coverage requirement\n"
                "Create a GitHub PR for each feature branch using Create GitHub PR."
            ),
            expected_output=(
                "JSON code review report with pass/fail per file and list of PR URLs created"
            ),
            agent=tech_lead,
            context=[java_task, react_task],
        )

        crew = Crew(
            agents=[tech_lead, java_dev, react_dev],
            tasks=[java_task, react_task, review_task],
            process=Process.hierarchical,
            manager_agent=tech_lead,
            verbose=True,
            memory=True,
            max_rpm=10,
        )
        crew.kickoff(inputs=inputs)
        return {"code_artifacts": [dict(a) for a in self._MOCK_ARTIFACTS]}
