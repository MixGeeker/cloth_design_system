# 服装制造文档原型引擎

这是通用服装几何和交付合同原型：人工审阅的结构规格 + 虚构成人身体参数 → 毫米纸样 SVG / 1:1 PDF、STL 饰件、BOM、中文制作说明和 Blender 工程预览。

**当前不是任意图片自动制版系统，也不是可直接投入工厂的已验证生产包。** 运行时视觉模型未配置；live 图像入口明确报错。reference replay 只接受已审阅参考图的精确校验和，绝不把固定模板伪装成 AI 分析。默认示例为原创中性几何合同夹具，不代表任何角色。

## 快速运行

Python 3.11+；可选 Blender 3.4+。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m clothforge.pipeline --out build
blender --background --python-exit-code 1 --python scripts/blender_preview.py -- --patterns build/A/patterns.json --profile build/A/profile.json --outdir build/A/preview
```

输出目录须为空；再次生成请使用新的 --out 路径，以免混入旧版本。

build/A、B、C 对应三组虚构成年测试数据。PDF 每页按裁片实际大小输出，并非统一 A4：选择实际尺寸打印，或使用阅读器海报分割；检查 20 mm 校准方框。SVG 采用毫米尺寸。STL 本身无单位，按 mm 导入切片器。

## 现有边界

- 可生成原始参数化主体、短下摆、分离袖、袖口、饰带等几何原型；按胸、腰、臀、躯干长度、手臂等分别变化，非整套等比缩放
- 环形饰件为原型，不含电子功能、承重保证或已验证皮肤接触材料
- 3D 为几何装配示意，未经布料仿真和实物试穿；平铺片与缝边图才是尺寸来源
- 未处理真实胸部塑形、人体扫描、自动面料辨识、机器排料、受力及工业放码
- 面料、闭合、背部构造、活动余量等推断必须保留可修改状态；先做坯布样衣
- 角色图片、角色特定规格与派生图纸不随公共代码发布。角色/IP 商用权不由本仓库授予
- 仓库暂未选定开源许可证；依赖各自遵循其许可，不继承其他项目许可证

## 架构与测试

见 [设计说明](docs/architecture_zh.md)。测试覆盖输入约束、显式失败、纸样几何、缝边匹配、刚体闭合、独立尺寸变化、交付清单和 PDF 物理页尺寸。实际运行结果以 CI 为准。
