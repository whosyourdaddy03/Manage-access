package com.ruoyi.visualization.mapper;

import com.ruoyi.visualization.domain.TrainingTask;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 训练任务 Mapper 接口
 */
public interface TrainingTaskMapper {

    /**
     * 查询所有训练任务
     */
    List<TrainingTask> selectTrainingTaskList();

    /**
     * 根据ID查询训练任务
     */
    TrainingTask selectTrainingTaskById(@Param("id") String id);

    /**
     * 插入训练任务
     */
    int insertTrainingTask(TrainingTask task);

    /**
     * 更新训练任务
     */
    int updateTrainingTask(TrainingTask task);

    /**
     * 从 annotations_epoch_results 同步任务ID
     */
    int syncTaskIds();

    /**
     * 按任务ID查询 epoch 结果
     */
    List<Map<String, Object>> selectEpochResultsByTaskId(@Param("id") String id);
}
