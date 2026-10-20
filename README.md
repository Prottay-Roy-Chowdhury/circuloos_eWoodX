# circuloos_eWoodX

This repository contains the development of the **eWoodX** project together with a reusable software framework for distributed computational, sensing, and robotic workflows.

The repository is organized into two main layers:

```text
circuloos_eWoodX/
│
├── framework/
│   └── Reusable framework components
│
└── projects/
    └── ewoodx/
        └── eWoodX-specific application
```

## Framework

The [`framework/`](framework/) package contains reusable components developed independently from the application-specific logic of eWoodX.

Its current capabilities include:

- communication and distributed Action lifecycle management;
- persistent bidirectional communication with Agent-aware streaming;
- generic TCP request-response and file transport;
- orchestration;
- persistent workspace and entity management;
- sensing and camera interfaces.


For the framework architecture, package structure, development principles, and detailed documentation, see:

**[Framework Documentation](framework/README.md)**

---

## eWoodX

The [`projects/ewoodx/`](projects/ewoodx/) package contains the application-specific implementation of the eWoodX workflow.

It integrates the reusable framework with project-specific:

- configuration;
- operations;
- orchestration;
- distributed agents;
- entrypoints;
- sensing and Timber data workflows;
- projection workflows.

For the project architecture, runtime structure, workflows, and links to the individual project packages, see:

**[eWoodX Project Documentation](projects/ewoodx/README.md)**

---

## Repository Structure

```text
circuloos_eWoodX/
│
├── framework/
│   ├── communication/
│   ├── orchestration/
│   ├── sensing/
│   ├── workspace/
│   ├── design/
│   └── robot_control/
│
├── projects/
│   └── ewoodx/
│       ├── agents/
│       ├── calibration_data/
│       ├── config/
│       ├── entrypoints/
│       ├── operations/
│       └── orchestration/
│
├── requirements.txt
└── README.md
```

Detailed documentation is maintained close to the corresponding implementation. Start with the framework or eWoodX documentation above and follow the linked package-level READMEs for lower-level details.

---

## Development Status

This repository is under active development. The framework and eWoodX application are being developed incrementally as the sensing, design, communication, and robotic workflow requirements evolve.