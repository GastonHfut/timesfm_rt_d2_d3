SET NAMES utf8mb4;
CREATE TABLE IF NOT EXISTS `epf_rt_d2_d3_forecast_result`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `forecast_date` date NOT NULL COMMENT '预测基准日期D，例如2026-11-27',
  `forecast_time` datetime NOT NULL COMMENT '预测目标时刻，属于D+2或D+3，按小时记录',
  `forecast_value` decimal(14, 4) NOT NULL COMMENT '实时电价预测值，单位元/MWh',
  `model_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型或融合方案名称',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_date_model_time`(`forecast_date`, `model_name`, `forecast_time`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'D+2和D+3实时电价小时预测结果表' ROW_FORMAT = Dynamic;
